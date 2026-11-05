"""
What each visitor turn says about the deal (M2-5): objections, competitors,
feature requests, buying signals.

Turns are classified in the background, never on the visitor's turn: the
``insights_classify`` job claims unclassified turns from the last week
(``FOR UPDATE SKIP LOCKED``, so replicas share the work), classifies each and
writes the result on the turn. The question text is the stored one, already
PII-masked (WS8), so neither the model nor this module sees a visitor's
details.

* Mock mode (and whenever the model fails or answers nonsense): deterministic
  keyword rules — ``rules``.
* Otherwise the lean (fast) model, asked for a small JSON object, parsed and
  checked by ``parse_model_output``; anything outside the known types is
  dropped. Competitors on the site's list are always found by name as well,
  so the list works even when the model misses one.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

OBJECTION_TYPES = ("price", "security", "integration", "effort", "trust", "timing")
OBJECTION_LABELS = {
    "price": "Price", "security": "Security & privacy", "integration": "Integrations",
    "effort": "Implementation effort", "trust": "Trust", "timing": "Timing",
}
MAX_REQUEST_CHARS = 200
BATCH = 50
LOOKBACK = "7 days"
# Model calls in flight at once, and how long one job run may keep going.
CONCURRENCY = 8
RUN_BUDGET_S = 15.0

_I = re.IGNORECASE
_OBJECTION_RULES: dict[str, re.Pattern] = {
    "price": re.compile(
        r"\b(too (expensive|pricey|costly|much)|expensive|pricey|over ?priced|can'?t afford|"
        r"afford|out of (our|my) budget|our budget|tight budget|cheaper|any discount|discounts?)\b", _I),
    "security": re.compile(
        r"\b(secure|security|gdpr|dpdp|soc ?2|iso ?27001|hipaa|complian\w*|encrypt\w*|"
        r"data (privacy|protection|leaks?|breach\w*|residency)|where is (my|our|the) data)\b", _I),
    "integration": re.compile(
        r"\b(integrat\w*|compatib\w*|connect (it )?(to|with)|works? with|plug-?ins?|sync with)\b", _I),
    "effort": re.compile(
        r"\b((hard|difficult|complicated|complex) to (set ?up|implement|install|use|learn|integrate)|"
        r"how long (does it take|to (set ?up|implement|onboard|go live))|setup time|"
        r"implementation (time|effort)|engineering (time|effort|resources)|steep learning)\b", _I),
    "trust": re.compile(
        r"\b(legit|trustworthy|reliable|reviews?|case stud\w*|references?|who (else )?uses|"
        r"track record|scam|never heard of|how many customers)\b", _I),
    "timing": re.compile(
        r"\b(not (right )?now|next (quarter|year|month)|later this year|not a priority|"
        r"maybe later|not ready|in a few (weeks|months)|after (the )?(holidays|quarter))\b", _I),
}
_WISH = re.compile(
    r"\b(i wish|would be (great|nice|good) if|please add|feature request|on (your|the) roadmap|"
    r"any plans? to|do you plan to|will you (add|support)|planning to (add|support)|missing)\b", _I)
_ASKS_FOR_FEATURE = re.compile(
    r"\b(do|does|can|will) (you|it|fluidbuddha|the (product|platform|tool)) "
    r"(support|have|offer|integrate with|work with|export|import)\b", _I)
_BUYING = re.compile(
    r"\b(how (do|can) (i|we) (buy|sign up|subscribe|get started|purchase|pay)|free trial|"
    r"start (a|the) trial|book (a|the) (demo|call|meeting)|(a|the) demo|talk to (sales|someone|a person)|"
    r"contract|invoice|quote|procurement|pricing for \d+|for \d+ (seats|users|people|agents)|"
    r"onboard (our|my) team|annual (plan|billing)|upgrade)\b", _I)

# Hindi and Hinglish wording of the same signals (M2-7), for the keyword rules
# (mock mode and the model's fallback). Devanagari words get no \b boundaries.
_HINDI_RULES = {
    "price": re.compile(r"(महंगा|महँगा|महंगी|बजट|डिस्काउंट|छूट|सस्ता|\b(mehenga|mehnga|mahanga|sasta)\b)", _I),
    "security": re.compile(r"(सुरक्षा|सुरक्षित|डेटा कहाँ)", _I),
    "integration": re.compile(r"(इंटीग्रेशन|इंटीग्रेट|कनेक्ट)", _I),
    "timing": re.compile(r"(अभी नहीं|बाद में|अगले (महीने|साल)|\b(abhi nahi|baad mein)\b)", _I),
}
_HINDI_BUYING = re.compile(r"(डेमो|ट्रायल|खरीद|कोटेशन|साइन अप|\b(demo chahiye|trial chahiye|kharid\w*)\b)", _I)



@dataclass
class Signals:
    objections: list[str] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    feature_request: Optional[str] = None
    buying_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"objections": self.objections, "competitors": self.competitors,
                "feature_request": self.feature_request, "buying_signal": self.buying_signal}


def _clean_list(values: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for v in values:
        if v not in seen:
            seen.append(v)
    return seen


def find_competitors(text: str, known: Iterable[str]) -> list[str]:
    """Names from the site's competitor list that appear as whole words."""
    out = []
    for name in known:
        name = (name or "").strip()
        if name and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, _I):
            out.append(name)
    return _clean_list(out)


def rules(question: str, *, competitors: Iterable[str] = (), found: bool = True) -> Signals:
    """Deterministic keyword classification. ``found``: whether the agent
    could answer from the site's content (an unanswered "do you support X?"
    reads as a feature request)."""
    q = question or ""
    feature = None
    if _WISH.search(q) or (not found and _ASKS_FOR_FEATURE.search(q)):
        feature = q.strip()[:MAX_REQUEST_CHARS]
    return Signals(
        objections=[t for t in OBJECTION_TYPES if _OBJECTION_RULES[t].search(q)
                    or (t in _HINDI_RULES and _HINDI_RULES[t].search(q))],
        competitors=find_competitors(q, competitors),
        feature_request=feature,
        buying_signal=bool(_BUYING.search(q) or _HINDI_BUYING.search(q)),
    )


PROMPT = """You label one question a website visitor asked a sales assistant.
Answer with ONE JSON object and nothing else:
{"objections": [...], "competitors": [...], "feature_request": null or "short text", "buying_signal": true/false}
- objections: concerns that could stop a purchase, only from: price, security, integration, effort, trust, timing.
  A plain question ("how much is it?") is not an objection; a worry ("that's too expensive") is.
- competitors: other products or companies the visitor names as alternatives. Known competitors: %s.
- feature_request: a capability the visitor wants that may not exist, in under 15 words; else null.
- buying_signal: true when the visitor shows intent to buy, trial, get a demo, talk to sales or sign a contract.
Text like [EMAIL_1] or [PHONE_1] is a masked detail: ignore it."""


def parse_model_output(raw: str, *, question: str, competitors: Iterable[str] = ()) -> Optional[Signals]:
    """The model's JSON, checked. None when it can't be used (the caller then
    falls back to ``rules``)."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    objections = data.get("objections") or []
    comps = data.get("competitors") or []
    feature = data.get("feature_request")
    if not isinstance(objections, list) or not isinstance(comps, list):
        return None
    known = list(competitors)
    names = [str(c).strip()[:60] for c in comps if isinstance(c, str) and c.strip()]
    # A name on the site's list keeps the list's spelling.
    canon = {k.lower(): k for k in known}
    names = [canon.get(n.lower(), n) for n in names]
    return Signals(
        objections=[t for t in OBJECTION_TYPES if t in {str(o).lower() for o in objections}],
        competitors=_clean_list(names + find_competitors(question, known))[:5],
        feature_request=(str(feature).strip()[:MAX_REQUEST_CHARS] or None)
        if isinstance(feature, str) and feature.strip().lower() not in ("", "null", "none") else None,
        buying_signal=data.get("buying_signal") is True,
    )


async def classify(question: str, *, competitors: Iterable[str] = (), found: bool = True,
                   llm: Any = None, model: Optional[str] = None,
                   tokens: Optional[list[int]] = None) -> Signals:
    """The model's reading when there is one, else the keyword rules. A model
    call adds its [input, output] tokens to ``tokens`` (for the usage record)."""
    competitors = list(competitors)
    if llm is None:
        return rules(question, competitors=competitors, found=found)
    from app.ai.base import ChatMessage

    try:
        resp = await llm.generate(
            system=PROMPT % (", ".join(competitors) or "none given"),
            messages=[ChatMessage(role="user", text=question[:1000])],
            model=model, temperature=0.0, max_output_tokens=160, thinking_budget=0,
        )
        if tokens is not None:
            from app.analytics.pricing import estimate_tokens

            tokens[0] += resp.input_tokens or estimate_tokens(PROMPT) + estimate_tokens(question[:1000])
            tokens[1] += resp.output_tokens or estimate_tokens(resp.text)
        parsed = parse_model_output(resp.text, question=question, competitors=competitors)
    except Exception as exc:
        logger.warning("turn classification failed, using rules: %s", exc)
        parsed = None
    return parsed or rules(question, competitors=competitors, found=found)


# ---- the background job ------------------------------------------------------------

async def classify_pending(db: Any, *, llm: Any = None, model: Optional[str] = None,
                           batch: int = BATCH) -> int:
    """Classify a batch of the last week's unclassified turns. Returns how many."""
    from sqlalchemy import text

    from app.orchestrator.profile import load_profile

    rows = (await db.execute(text(
        "SELECT id, site_key, question, found, intent FROM conversation_turns "
        f"WHERE classified_at IS NULL AND created_at > now() - interval '{LOOKBACK}' "
        # Newest first: a fresh conversation shows within a minute even while
        # a backlog drains.
        "ORDER BY created_at DESC LIMIT :n FOR UPDATE SKIP LOCKED"), {"n": batch})).mappings().all()
    known: dict[str, list[str]] = {}
    for r in rows:
        if r["site_key"] not in known:
            known[r["site_key"]] = (await load_profile(db, r["site_key"])).competitors
    gate = asyncio.Semaphore(CONCURRENCY)
    spent: dict[str, list[int]] = {}   # site → [input, output] tokens

    async def one(r: Any) -> Signals:
        if r["intent"] == "greeting" or (r["question"] or "").startswith("("):
            return Signals()   # small talk, or a synthetic turn like the welcome
        async with gate:
            return await classify(r["question"], competitors=known[r["site_key"]],
                                  found=bool(r["found"]), llm=llm, model=model,
                                  tokens=spent.setdefault(r["site_key"], [0, 0]))

    results = await asyncio.gather(*(one(r) for r in rows))
    for r, sig in zip(rows, results):
        await db.execute(text(
            "UPDATE conversation_turns SET objections = :o, competitors = :c, feature_request = :f, "
            "buying_signal = :b, classified_at = now() WHERE id = :id"),
            {"o": sig.objections, "c": sig.competitors, "f": sig.feature_request,
             "b": sig.buying_signal, "id": r["id"]})
    await db.commit()
    # The labelling's model cost goes on each site's usage and cost (M2-5 follow-up).
    from app.analytics.usage import record_background

    for site_key, (tin, tout) in spent.items():
        await record_background(db, site_key, input_tokens=tin, output_tokens=tout)
    return len(rows)


async def run_job(session_factory: Any, *, llm: Any = None, model: Optional[str] = None,
                  budget_s: float = RUN_BUDGET_S) -> int:
    """One scheduler run: classify batches until none are left or the time
    budget is spent. Returns how many turns were classified."""
    loop = asyncio.get_running_loop()
    end, total = loop.time() + budget_s, 0
    while loop.time() < end:
        async with session_factory() as db:
            n = await classify_pending(db, llm=llm, model=model)
        total += n
        if n < BATCH:
            break
    return total
