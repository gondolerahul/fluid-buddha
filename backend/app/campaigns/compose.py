"""
Composing a campaign's landing page (M3-1), grounded.

1. **Context** from the link: the persona (``?persona=``, else ``utm_content``
   if it names one, else the campaign's), the visitor's question (``?q=``,
   else ``utm_term``), the language, the arm. ``?account=`` only personalises
   the page as it's drawn, so it never costs a composition.
2. **Material**: the site's knowledge retrieved for the campaign's messages,
   the persona's focus and the question (``S1``…, above the grounding
   threshold only); the tenant's pinned answers (``G1``…); the questions it
   blocked; the proof the campaign supplies (testimonials, logos).
3. **Composition**: the account's model (M3-4) or the platform's, asked for
   typed sections that cite their sources; without a model (mock mode) or if
   it fails, a rule-based composer that only quotes the material.
4. **Enforcement**, whatever composed it (``enforce``): only the campaign's
   sections; every factual section cites real sources; every number on the
   page appears in what it cites (or in the campaign's own copy); testimonials
   and logos only as the customer gave them; pinned answers word for word;
   blocked questions never answered; the enquiry form is always the same safe
   one. What fails is dropped, and the drop is recorded on the page spec.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.campaigns.store import ALWAYS, Campaign
from app.cortex.episodic import normalize_question
from app.orchestrator.pagegen import SECTION_TYPES

logger = logging.getLogger(__name__)

MAX_SECTIONS = 10
_ACCOUNT_RE = re.compile(r"[^\w &.,'-]+", re.UNICODE)
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z0-9ऀ-ॿ]+")
_STOP = set("a an and are as at be by can do does for from has have how i in is it its me my of on or our "
            "so that the their this to us we what when which who why will with you your about into more "
            "get any all".split())
_FACTUAL = {"feature_grid", "text", "pricing_table", "faq", "comparison", "chart"}

CHROME = {
    "en": {"faq": "Questions people ask", "features": "Why it fits", "proof": "What customers say",
           "logos": "Trusted by", "enquiry": "Talk to the team", "send": "Send", "answer": "Your question",
           "cta": "Ready when you are", "roi": "Estimate your return"},
    "hi": {"faq": "लोग जो पूछते हैं", "features": "यह क्यों सही है", "proof": "ग्राहक क्या कहते हैं",
           "logos": "इन पर भरोसा", "enquiry": "टीम से बात करें", "send": "भेजें", "answer": "आपका सवाल",
           "cta": "जब आप तैयार हों", "roi": "अपना फ़ायदा आँकिए"},
}


@dataclass
class Context:
    arm: str = "a"
    persona: Optional[str] = None
    question: Optional[str] = None
    account: Optional[str] = None
    lang: str = "en"
    source: Optional[str] = None


def context_from(params: dict[str, str], c: Campaign, *, personas: list[str], languages: list[str],
                 arm: str = "a") -> Context:
    """What the link asks for, cleaned."""
    def pick(*names: str) -> str:
        for n in names:
            v = " ".join(str(params.get(n) or "").split())
            if v:
                return v
        return ""

    persona = pick("persona").lower()
    if persona not in personas:
        hint = pick("utm_content").lower()
        persona = hint if hint in personas else (c.persona or "")
    question = pick("q", "utm_term")[:200] or None
    account = _ACCOUNT_RE.sub("", pick("account"))[:60].strip() or None
    lang = pick("lang").lower()
    lang = lang if lang in ("en", "hi") and lang in (languages or ["en"]) else "en"
    source = pick("utm_source")[:60].lower() or None
    return Context(arm=arm, persona=persona or None, question=question, account=account, lang=lang,
                   source=source)


# ---- material ------------------------------------------------------------------------

@dataclass
class Material:
    sources: dict[str, dict[str, Any]]       # S1.. -> {text, label, route, document}
    golden: dict[str, dict[str, str]]        # G1.. -> {q, a}
    blocked: set[str]                        # normalised questions never answered


def _words(s: str) -> set[str]:
    return {w for w in _WORD_RE.findall((s or "").lower()) if w not in _STOP and len(w) > 1}


def _sentences(s: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+|\n+", s or "")
    return [p.strip(" -•*#\t") for p in parts if len(p.strip()) > 20]


async def gather(db: AsyncSession, bridge: Any, c: Campaign, ctx: Context, *, persona_focus: str,
                 threshold: float, top_k: int = 8) -> Material:
    from app.cortex.query import _label, _route

    brief = c.brief(ctx.arm)
    queries = [q for q in (ctx.question, " ".join(brief["key_messages"][:4]) or c.name,
                           f"{persona_focus} {c.audience}".strip(), c.goal) if q]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for q in queries:
        try:
            found = await bridge.search(q, top_k=top_k)
        except Exception as exc:
            logger.warning("campaign retrieval failed: %s", exc)
            found = []
        for r in found:
            body = (r.get("content") or "").strip()
            if not body or float(r.get("score") or 0) < threshold or body in seen:
                continue
            seen.add(body)
            rows.append(r)
    sources: dict[str, dict[str, Any]] = {}
    for i, r in enumerate(rows[:top_k * 2], start=1):
        name = (r.get("source_ref") or {}).get("filename") or r.get("document_title") or ""
        sources[f"S{i}"] = {"text": r["content"].strip()[:1500], "label": _label(name) if name else "Site content",
                            "route": _route(name) if name else None, "document": r.get("document_title")}
    gold = (await db.execute(text(
        "SELECT question, answer_text FROM conversation_cache WHERE site_key = :s AND kind = 'turn' "
        "AND status = 'pinned' ORDER BY hit_count DESC NULLS LAST LIMIT 20"), {"s": c.site_key})).all()
    blocked = {normalize_question(r[0]) for r in (await db.execute(text(
        "SELECT question FROM conversation_cache WHERE site_key = :s AND status = 'blocked'"),
        {"s": c.site_key})).all()}
    golden = {f"G{i}": {"q": q, "a": a} for i, (q, a) in enumerate(gold, start=1) if q and a}
    return Material(sources=sources, golden=golden, blocked=blocked)


# ---- enforcement ---------------------------------------------------------------------

def _numbers(s: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM_RE.findall(s or "")}


def _strings(v: Any) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return [s for x in v.values() for s in _strings(x)]
    if isinstance(v, list):
        return [s for x in v for s in _strings(x)]
    return []


def _clip(v: Any, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def _campaign_text(c: Campaign, arm: str) -> str:
    b = c.brief(arm)
    return " ".join([c.name, c.goal, c.audience, b["headline"], b["cta_label"], *b["key_messages"]])


def enforce(sections: Any, *, c: Campaign, m: Material, arm: str, lang: str = "en"
            ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Keep only what the campaign allows and the material supports."""
    allowed = set(c.sections) | set(ALWAYS)
    own = _campaign_text(c, arm)
    everything = own + " " + " ".join(s["text"] for s in m.sources.values()) + " " + " ".join(
        g["q"] + " " + g["a"] for g in m.golden.values())
    quotes = {normalize_question(t["quote"]): t for t in c.testimonials}
    logos = {lg["src"]: lg for lg in c.logos}
    golden_by_q = {normalize_question(g["q"]): g for g in m.golden.values()}
    out: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []

    def drop(t: str, why: str) -> None:
        dropped.append({"type": t, "reason": why})

    for s in sections if isinstance(sections, list) else []:
        if not isinstance(s, dict):
            continue
        t = str(s.get("type") or "")
        props = s.get("props") if isinstance(s.get("props"), dict) else {}
        cites = [x for x in (s.get("sources") or []) if isinstance(x, str)]
        if t not in SECTION_TYPES or t not in allowed:
            drop(t or "?", "not allowed in this campaign")
            continue
        if any(x["type"] == t for x in out) and t in ALWAYS:
            continue
        valid = [x for x in cites if x in m.sources or x in m.golden or x == "campaign"]
        corpus = own + " " + " ".join(m.sources[x]["text"] if x in m.sources else
                                      (m.golden[x]["q"] + " " + m.golden[x]["a"]) if x in m.golden else ""
                                      for x in valid)

        if t == "testimonials":
            items = [quotes[normalize_question(str((i or {}).get("quote") or ""))] for i in props.get("items") or []
                     if normalize_question(str((i or {}).get("quote") or "")) in quotes]
            if not items:
                drop(t, "no testimonial the customer supplied")
                continue
            out.append({"type": t, "props": {"title": _clip(props.get("title"), 80), "items": items[:6]},
                        "sources": ["campaign"]})
            continue
        if t == "logos":
            items = [logos[str((i or {}).get("src"))] for i in props.get("items") or []
                     if str((i or {}).get("src")) in logos]
            if not items:
                drop(t, "no logo the customer supplied")
                continue
            out.append({"type": t, "props": {"title": _clip(props.get("title"), 80), "items": items[:12]},
                        "sources": ["campaign"]})
            continue
        if t == "enquiry_form":
            ch = CHROME[lang]
            out.append({"type": t, "props": {"title": _clip(props.get("title"), 80) or ch["enquiry"],
                                             "submit_label": _clip(props.get("submit_label"), 40) or ch["send"]},
                        "sources": []})
            continue
        if t == "roi_calculator":
            nums = {}
            for k, hi in (("seats", 10000), ("monthly_cost", 10_000_000), ("hours_saved", 100000),
                          ("hourly_value", 100000)):
                v = props.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= hi:
                    nums[k] = v
            out.append({"type": t, "props": {"title": _clip(props.get("title"), 80) or CHROME[lang]["roi"], **nums},
                        "sources": []})
            continue
        if t == "media":
            src = str(props.get("src") or "")
            if src not in logos:
                drop(t, "images only from the campaign")
                continue
            out.append({"type": t, "props": {"src": src, "alt": _clip(props.get("alt"), 120),
                                             "caption": _clip(props.get("caption"), 160)}, "sources": ["campaign"]})
            continue
        if t == "faq":
            items = []
            for i in props.get("items") or []:
                q, a = _clip((i or {}).get("q"), 200), _clip((i or {}).get("a"), 900)
                nq = normalize_question(q)
                if not q or nq in m.blocked:
                    continue
                if nq in golden_by_q:          # the tenant's approved answer, word for word
                    items.append({"q": golden_by_q[nq]["q"], "a": golden_by_q[nq]["a"]})
                elif a and valid and _numbers(a) <= _numbers(corpus):
                    items.append({"q": q, "a": a})
            if not items:
                drop(t, "no grounded answers")
                continue
            out.append({"type": t, "props": {"title": _clip(props.get("title"), 80), "items": items[:8]},
                        "sources": valid})
            continue

        # hero, cta, feature_grid, text, pricing_table, comparison, chart
        if t in _FACTUAL and not valid:
            drop(t, "cites no sources")
            continue
        words = " ".join(_strings(props))
        basis = everything if t in ALWAYS else corpus
        missing = _numbers(words) - _numbers(basis)
        if missing:
            drop(t, "numbers not in its sources: " + ", ".join(sorted(missing)[:4]))
            continue
        clean = _clean_props(t, props)
        if clean is None:
            drop(t, "empty")
            continue
        out.append({"type": t, "props": clean, "sources": valid})
        if len(out) >= MAX_SECTIONS:
            break
    # Every page opens with a hero and ends with the call to action.
    if not any(s["type"] == "hero" for s in out):
        b = c.brief(arm)
        out.insert(0, {"type": "hero", "props": {"title": b["headline"] or (b["key_messages"] or [c.name])[0],
                                                 "cta_label": b["cta_label"]}, "sources": ["campaign"]})
    else:
        out.sort(key=lambda s: s["type"] != "hero")
    if c.cta_label or c.brief(arm)["cta_label"]:
        if not any(s["type"] == "cta" for s in out):
            out.append({"type": "cta", "props": {"title": CHROME[lang]["cta"],
                                                 "cta_label": c.brief(arm)["cta_label"]}, "sources": ["campaign"]})
        else:
            out.sort(key=lambda s: s["type"] == "cta")
    return out, dropped


def _clean_props(t: str, p: dict[str, Any]) -> Optional[dict[str, Any]]:
    if t == "hero":
        title = _clip(p.get("title"), 160)
        return {"title": title, "subtitle": _clip(p.get("subtitle"), 300),
                "cta_label": _clip(p.get("cta_label"), 60)} if title else None
    if t == "cta":
        return {"title": _clip(p.get("title"), 120), "body": _clip(p.get("body"), 300),
                "cta_label": _clip(p.get("cta_label"), 60)}
    if t == "text":
        body = _clip(p.get("body"), 1500)
        return {"title": _clip(p.get("title"), 160), "body": body} if body else None
    if t == "feature_grid":
        items = [{"title": _clip(i.get("title"), 100), "body": _clip(i.get("body"), 400)}
                 for i in p.get("items") or [] if isinstance(i, dict) and i.get("title")][:6]
        return {"title": _clip(p.get("title"), 120), "items": items} if items else None
    if t == "pricing_table":
        tiers = [{"name": _clip(i.get("name"), 60), "price": _clip(i.get("price"), 40),
                  "features": [_clip(f, 120) for f in (i.get("features") or [])[:8]]}
                 for i in p.get("tiers") or [] if isinstance(i, dict) and i.get("name")][:4]
        return {"title": _clip(p.get("title"), 120), "tiers": tiers} if tiers else None
    if t == "comparison":
        cols = [_clip(x, 60) for x in (p.get("columns") or [])[:4]]
        rows = [{"label": _clip(r.get("label"), 100), "values": [_clip(v, 100) for v in (r.get("values") or [])[:4]]}
                for r in p.get("rows") or [] if isinstance(r, dict) and r.get("label")][:12]
        return {"title": _clip(p.get("title"), 120), "columns": cols, "rows": rows} if cols and rows else None
    if t == "chart":
        data = [{"label": _clip(d.get("label"), 40), "value": d["value"]} for d in p.get("data") or []
                if isinstance(d, dict) and isinstance(d.get("value"), (int, float))][:12]
        ctype = p.get("chart_type") if p.get("chart_type") in ("bar", "line", "pie") else "bar"
        return {"chart_type": ctype, "title": _clip(p.get("title"), 120), "unit": _clip(p.get("unit"), 12),
                "data": data} if data else None
    return None


# ---- composers -----------------------------------------------------------------------

def _best(m: Material, query: str, used: set[str]) -> Optional[tuple[str, str]]:
    """The sentence of the material that shares most words with ``query``."""
    q = _words(query)
    best: tuple[int, str, str] | None = None
    for sid, s in m.sources.items():
        for sent in _sentences(s["text"]):
            if sent in used:
                continue
            score = len(q & _words(sent))
            if score and (best is None or score > best[0]):
                best = (score, sid, sent[:400])
    if best is None:
        return None
    used.add(best[2])
    return best[1], best[2]


def compose_rules(c: Campaign, ctx: Context, m: Material, *, persona_label: str = "",
                  persona_focus: str = "") -> list[dict[str, Any]]:
    """Without a model: a page that only quotes the material."""
    b = c.brief(ctx.arm)
    ch = CHROME[ctx.lang]
    used: set[str] = set()
    msgs = b["key_messages"] or [c.name]
    lead = _best(m, f"{persona_focus} {c.audience} {msgs[0]}", used)
    sections: list[dict[str, Any]] = [{"type": "hero", "props": {
        "title": b["headline"] or msgs[0], "subtitle": lead[1] if lead else "", "cta_label": b["cta_label"]},
        "sources": [lead[0]] if lead else ["campaign"]}]
    if ctx.question and normalize_question(ctx.question) not in m.blocked:
        gold = next((g for g in m.golden.values() if normalize_question(g["q"]) == normalize_question(ctx.question)),
                    None)
        if gold:
            sections.append({"type": "faq", "props": {"title": ch["answer"], "items": [gold]},
                             "sources": [k for k, g in m.golden.items() if g is gold]})
        else:
            ans = [x for x in (_best(m, ctx.question, used), _best(m, ctx.question, used)) if x]
            if ans:
                sections.append({"type": "text", "props": {"title": ctx.question, "body": " ".join(a[1] for a in ans)},
                                 "sources": list(dict.fromkeys(a[0] for a in ans))})
    items, cites = [], []
    for msg in (msgs[1:4] if len(msgs) > 1 else msgs):
        hit = _best(m, f"{msg} {persona_focus}", used)
        if hit:
            items.append({"title": msg, "body": hit[1]})
            cites.append(hit[0])
    if items:
        sections.append({"type": "feature_grid", "props": {"title": ch["features"], "items": items},
                         "sources": list(dict.fromkeys(cites))})
    if c.testimonials:
        sections.append({"type": "testimonials", "props": {"title": ch["proof"], "items": c.testimonials},
                         "sources": ["campaign"]})
    if c.logos:
        sections.append({"type": "logos", "props": {"title": ch["logos"], "items": c.logos}, "sources": ["campaign"]})
    focus = _words(f"{persona_focus} {c.audience} {ctx.question or ''} {' '.join(msgs)}")
    golden = sorted(m.golden.items(), key=lambda kv: -len(focus & _words(kv[1]["q"])))
    faq = [(k, g) for k, g in golden if normalize_question(g["q"]) not in m.blocked][:4]
    if faq:
        sections.append({"type": "faq", "props": {"title": ch["faq"], "items": [g for _, g in faq]},
                         "sources": [k for k, _ in faq]})
    sections.append({"type": "roi_calculator", "props": {"title": ch["roi"]}, "sources": []})
    sections.append({"type": "enquiry_form", "props": {}, "sources": []})
    sections.append({"type": "cta", "props": {"title": ch["cta"], "cta_label": b["cta_label"]},
                     "sources": ["campaign"]})
    return sections


COMPOSE_PROMPT = """You compose a landing page for a company's campaign, as typed sections.
Use ONLY the material given: SOURCES (S1..), APPROVED ANSWERS (G1..) and the CAMPAIGN brief.
Rules:
- Each section is {type, props, sources}; sources lists the ids it is based on ("campaign" for the brief).
- Every fact, feature, price and number must come from the sources it cites. Never invent numbers.
- Testimonials and logos: only the ones under PROOF, quoted exactly. Never write your own.
- An approved answer is used word for word.
- Write for the persona and answer the visitor's question first if there is one.
- Write in {lang}. Short, concrete copy. 5-9 sections. Start with a hero, end with a cta.
Call compose_page once."""


def _tool_spec() -> Any:
    from app.ai.base import ToolSpec

    return ToolSpec(name="compose_page", description="The composed landing page.", parameters={
        "type": "object", "properties": {
            "title": {"type": "string"},
            "sections": {"type": "array", "items": {"type": "object", "properties": {
                "type": {"type": "string"}, "props": {"type": "object"},
                "sources": {"type": "array", "items": {"type": "string"}}},
                "required": ["type", "props", "sources"]}}},
        "required": ["title", "sections"]})


def _material_prompt(c: Campaign, ctx: Context, m: Material, persona_label: str, persona_focus: str) -> str:
    b = c.brief(ctx.arm)
    allowed = [*ALWAYS, *c.sections]
    lines = [f"CAMPAIGN: {c.name}", f"Goal: {c.goal}", f"Audience: {c.audience}",
             "Key messages: " + " | ".join(b["key_messages"]),
             f"Headline (use it): {b['headline']}" if b["headline"] else "",
             f"Call to action label: {b['cta_label']}",
             "ALLOWED SECTIONS: " + "; ".join(f"{t}: {SECTION_TYPES[t]}" for t in allowed),
             f"PERSONA: {persona_label} — {persona_focus}" if persona_label else "PERSONA: a general visitor",
             f"VISITOR'S QUESTION: {ctx.question}" if ctx.question else "",
             "SOURCES:"] + [f"[{k}] {s['text']}" for k, s in m.sources.items()]
    if m.golden:
        lines += ["APPROVED ANSWERS:"] + [f"[{k}] Q: {g['q']} A: {g['a']}" for k, g in m.golden.items()]
    if m.blocked:
        lines.append("NEVER ANSWER: " + " | ".join(sorted(m.blocked)[:20]))
    if c.testimonials or c.logos:
        lines.append("PROOF:")
        lines += [f'testimonial: "{t["quote"]}" — {t["name"]}, {t.get("role") or ""}' for t in c.testimonials]
        lines += [f"logo: src={lg['src']} alt={lg['alt']}" for lg in c.logos]
    return "\n".join(x for x in lines if x)


async def compose_llm(llm: Any, model: Optional[str], c: Campaign, ctx: Context, m: Material,
                      persona_label: str, persona_focus: str) -> Optional[tuple[list[dict], int, int]]:
    from app.ai.base import ChatMessage

    try:
        resp = await llm.generate(
            system=COMPOSE_PROMPT.replace("{lang}", "Hindi" if ctx.lang == "hi" else "English"),
            messages=[ChatMessage(role="user", text=_material_prompt(c, ctx, m, persona_label, persona_focus))],
            tools=[_tool_spec()], model=model, temperature=0.3, max_output_tokens=4000)
    except Exception as exc:
        logger.warning("campaign composition failed, using the rules: %s", exc)
        return None
    call = next((tc for tc in resp.tool_calls if tc.name == "compose_page"), None)
    if call is None or not isinstance(call.args.get("sections"), list):
        return None
    return call.args["sections"], resp.input_tokens, resp.output_tokens


async def compose(db: AsyncSession, rt: Any, c: Campaign, ctx: Context, *, llm: Any = None,
                  model: Optional[str] = None) -> dict[str, Any]:
    """The page spec: ``{title, lang, persona, question, sections, sources, composer, dropped, build_ms}``."""
    from app.orchestrator.profile import profile_for

    t0 = time.monotonic()
    profile = profile_for(c.site_key)
    persona = profile.persona(ctx.persona) if ctx.persona else None
    label, focus = (persona.label, persona.focus) if persona else ("", "")
    bridge = rt.bridge(db, site_key=c.site_key)
    m = await gather(db, bridge, c, ctx, persona_focus=focus,
                     threshold=rt.settings.cortex_confidence_threshold)
    composer, raw, tokens = "rules", None, (0, 0)
    if llm is not None:
        got = await compose_llm(llm, model, c, ctx, m, label, focus)
        if got is not None:
            raw, tokens, composer = got[0], (got[1], got[2]), "model"
    if raw is None:
        raw = compose_rules(c, ctx, m, persona_label=label, persona_focus=focus)
    sections, dropped = enforce(raw, c=c, m=m, arm=ctx.arm, lang=ctx.lang)
    if composer == "model" and sum(1 for s in sections if s["type"] not in ALWAYS) < 2:
        # The model's page didn't survive the checks: the rules' page instead.
        composer = "rules"
        sections, more = enforce(compose_rules(c, ctx, m, persona_label=label, persona_focus=focus),
                                 c=c, m=m, arm=ctx.arm, lang=ctx.lang)
        dropped += more
    cited = {x for s in sections for x in s["sources"]}
    return {
        "title": (c.brief(ctx.arm)["headline"] or c.name), "lang": ctx.lang, "arm": ctx.arm,
        "persona": ctx.persona, "persona_label": label, "question": ctx.question, "sections": sections,
        "sources": {k: {kk: v for kk, v in s.items() if kk != "text"} for k, s in m.sources.items() if k in cited},
        "composer": composer, "dropped": dropped, "tokens": list(tokens),
        "build_ms": int((time.monotonic() - t0) * 1000),
    }
