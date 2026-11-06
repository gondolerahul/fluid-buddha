"""
Silent intent resolver (P1-2, strategy §4.4).

A visitor who hasn't said anything still sends signals: the landing path, UTM
tags, the referrer and any search terms. ``resolve_intent`` maps them onto one
of the site's intent families without blocking on a model:

1. **Rules** the owner wrote (path / UTM / referrer / query globs), highest
   priority first → confidence 0.9.
2. **Embeddings**: cosine similarity between the signal text and each family's
   label + description → the best family at or above ``EMBED_THRESHOLD``.
3. Otherwise the ``general`` family. If a model is available, a background
   classification with the fast model runs and its answer is remembered for
   that signal fingerprint for 24 hours, so the *next* visitor with the same
   signals gets it. Nobody waits for it.
"""
from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional
from urllib.parse import parse_qs, urlsplit

from app.experience.regions_store import IntentFamily, normalize_page

logger = logging.getLogger(__name__)

GENERAL = "general"
RULE_CONFIDENCE = 0.9
EMBED_THRESHOLD = 0.6
_MODEL_TTL_S = 24 * 3600
_SEARCH_PARAMS = ("q", "query", "p", "search", "text", "wd")
_WORD_RE = re.compile(r"[a-z0-9ऀ-ॿ]+")

Embed = Callable[[str], Awaitable[Optional[list[float]]]]


@dataclass
class Signals:
    page: str = "/"
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_term: str = ""
    referrer: str = ""
    query: str = ""
    lang: str = "en"
    persona: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None, *, page: str = "/", lang: str = "en",
                  persona: str = "") -> "Signals":
        r = dict(raw or {})

        def s(k: str, n: int = 200) -> str:
            return str(r.get(k) or "").strip().lower()[:n]

        return cls(page=normalize_page(page or r.get("page")), utm_source=s("utm_source"),
                   utm_medium=s("utm_medium"), utm_campaign=s("utm_campaign"), utm_term=s("utm_term"),
                   referrer=str(r.get("referrer") or "")[:500], query=s("q", 300),
                   lang=lang or "en", persona=persona or "")

    @property
    def referrer_host(self) -> str:
        try:
            return (urlsplit(self.referrer).hostname or "").lower()
        except ValueError:
            return ""

    @property
    def referrer_terms(self) -> str:
        """Search terms a referrer passes on (rare today, but free when present)."""
        try:
            qs = parse_qs(urlsplit(self.referrer).query)
        except ValueError:
            return ""
        for k in _SEARCH_PARAMS:
            if qs.get(k):
                return qs[k][0].lower()[:200]
        return ""

    def text(self) -> str:
        """The signal text compared with family descriptions."""
        path_words = " ".join(_WORD_RE.findall(self.page.replace("-", " ").replace("_", " ")))
        bits = [path_words, self.utm_campaign.replace("-", " ").replace("_", " "),
                self.utm_term, self.query, self.referrer_terms]
        return " ".join(b for b in bits if b).strip()

    def fingerprint(self, site_key: str) -> str:
        raw = json.dumps([site_key, self.page, self.utm_source, self.utm_medium, self.utm_campaign,
                          self.utm_term, self.referrer_host, self.query, self.referrer_terms])
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class Intent:
    family: str = GENERAL
    label: str = "General visitor"
    stage: str = ""
    confidence: float = 0.0
    source: str = "default"            # rule | embedding | model | default
    matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "label": self.label, "stage": self.stage,
                "confidence": round(self.confidence, 3), "source": self.source, "matched": self.matched}


def _glob_any(value: str, patterns: list[str]) -> Optional[str]:
    if not value:
        return None
    for p in patterns:
        if fnmatch.fnmatchcase(value, p):
            return p
    return None


def rule_match(fam: IntentFamily, sig: Signals) -> list[str]:
    """Which of a family's rules the signals satisfy (any one is enough)."""
    hits: list[str] = []
    r = fam.rules
    if (p := _glob_any(sig.page, r.get("paths", []))):
        hits.append(f"path {p}")
    for key in ("utm_source", "utm_medium", "utm_campaign"):
        if (p := _glob_any(getattr(sig, key), r.get(key, []))):
            hits.append(f"{key} {p}")
    if (p := _glob_any(sig.referrer_host, r.get("referrer_hosts", []))):
        hits.append(f"referrer {p}")
    terms = r.get("query_terms", [])
    if terms:
        hay = " ".join([sig.query, sig.utm_term, sig.referrer_terms])
        words = set(_WORD_RE.findall(hay))
        for t in terms:
            if (" " in t and t in hay) or t in words:
                hits.append(f"query '{t}'")
                break
    return hits


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _general(families: list[IntentFamily]) -> Intent:
    g = next((f for f in families if f.slug == GENERAL), None)
    return Intent(family=GENERAL, label=g.label if g else "General visitor", stage=g.stage if g else "")


# Family embeddings, by (site, slug, updated_at): text → vector.
_family_vectors: dict[tuple[str, str, str], list[float]] = {}
# Background model answers, by signal fingerprint: (expires_at, slug).
_model_answers: dict[str, tuple[float, str]] = {}
_model_inflight: set[str] = set()


async def _family_vector(site_key: str, fam: IntentFamily, embed: Embed) -> Optional[list[float]]:
    key = (site_key, fam.slug, str(fam.updated_at))
    if key in _family_vectors:
        return _family_vectors[key]
    vec = await embed(f"{fam.label}. {fam.description} {fam.stage}".strip())
    if vec:
        _family_vectors[key] = vec
    return vec


async def resolve_intent(
    site_key: str,
    families: list[IntentFamily],
    sig: Signals,
    *,
    embed: Optional[Embed] = None,
    classify: Optional[Callable[[list[IntentFamily], Signals], Awaitable[Optional[str]]]] = None,
) -> Intent:
    active = [f for f in families if f.enabled]
    candidates = [f for f in active if f.slug != GENERAL]

    # 1. Rules, highest priority first (families come sorted by priority).
    for fam in sorted(candidates, key=lambda f: -f.priority):
        hits = rule_match(fam, sig)
        if hits:
            return Intent(fam.slug, fam.label, fam.stage, RULE_CONFIDENCE, "rule", hits)

    # A remembered background classification for these exact signals.
    fp = sig.fingerprint(site_key)
    remembered = _model_answers.get(fp)
    if remembered and remembered[0] > time.monotonic():
        fam = next((f for f in candidates if f.slug == remembered[1]), None)
        if fam:
            return Intent(fam.slug, fam.label, fam.stage, 0.7, "model", ["remembered classification"])

    # 2. Embedding nearest neighbour.
    text = sig.text()
    if embed is not None and text and candidates:
        try:
            qv = await embed(text)
        except Exception as exc:  # embeddings are optional
            logger.debug("intent embed failed: %s", exc)
            qv = None
        if qv:
            best: tuple[float, Optional[IntentFamily]] = (0.0, None)
            for fam in candidates:
                fv = await _family_vector(site_key, fam, embed)
                if fv:
                    sim = _cosine(qv, fv)
                    if sim > best[0]:
                        best = (sim, fam)
            if best[1] is not None and best[0] >= EMBED_THRESHOLD:
                f = best[1]
                return Intent(f.slug, f.label, f.stage, best[0], "embedding", [f"similar to '{f.label}'"])

    # 3. Default now; classify in the background for next time.
    if classify is not None and candidates and text and fp not in _model_inflight:
        _model_inflight.add(fp)

        async def run() -> None:
            try:
                slug = await classify(candidates, sig)
                if slug and any(f.slug == slug for f in candidates):
                    _model_answers[fp] = (time.monotonic() + _MODEL_TTL_S, slug)
            except Exception as exc:
                logger.debug("background intent classification failed: %s", exc)
            finally:
                _model_inflight.discard(fp)

        asyncio.get_running_loop().create_task(run())
    return _general(active)


def clear_intent_caches() -> None:
    _family_vectors.clear()
    _model_answers.clear()
    _model_inflight.clear()


# ---- suggestions from the site's routes --------------------------------------

_SUGGESTIONS: list[tuple[tuple[str, ...], str, str, str, str]] = [
    (("pricing", "plans", "price"), "compare-plans", "Comparing plans and prices",
     "Weighing up plans, prices and what each includes.", "evaluate"),
    (("demo", "contact", "book", "trial", "signup", "get-started"), "ready-to-talk", "Ready to talk",
     "Wants a demo, a trial or to speak to someone.", "buy"),
    (("integration", "integrations", "api", "developers", "docs"), "integration-check", "Checking integrations",
     "Wants to know how it fits with their tools and systems.", "evaluate"),
    (("security", "trust", "compliance", "privacy"), "security-review", "Security review",
     "Checking security, compliance and data handling.", "evaluate"),
    (("customers", "case-studies", "stories", "testimonials"), "seeking-proof", "Looking for proof",
     "Wants evidence that it works for businesses like theirs.", "evaluate"),
    (("vs", "compare", "alternative", "alternatives"), "comparing-alternatives", "Comparing alternatives",
     "Comparing this with competitors or other options.", "evaluate"),
    (("features", "product", "how-it-works", "platform"), "understand-product", "Understanding the product",
     "Learning what the product does and how it works.", "learn"),
    (("support", "help", "faq"), "existing-customer", "Existing customer",
     "Already a customer looking for help.", "customer"),
]


def suggest_families(routes: list[str], personas: list[tuple[str, str]] | None = None) -> list[dict[str, Any]]:
    """Proposed families from the site's routes (and audience pages), not saved."""
    out: dict[str, dict[str, Any]] = {}
    for route in routes:
        path = normalize_page(route)
        words = set(_WORD_RE.findall(path.replace("-", " "))) | {path.strip("/").split("/")[0]}
        for keys, slug, label, desc, stage in _SUGGESTIONS:
            if words & set(keys) or any(k in path for k in keys if "-" in k):
                fam = out.setdefault(slug, {"slug": slug, "label": label, "description": desc,
                                            "stage": stage, "rules": {"paths": []}, "priority": 0})
                glob = path + "*" if path != "/" else "/"
                if glob not in fam["rules"]["paths"]:
                    fam["rules"]["paths"].append(glob)
    for slug, label in personas or []:
        s = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-")[:30] or "persona"
        out.setdefault(f"for-{s}", {"slug": f"for-{s}"[:40], "label": f"{label} exploring",
                                    "description": f"A {label} visitor learning what fits them.",
                                    "stage": "learn", "rules": {"paths": [f"/for/{s}*"]}, "priority": 0})
    out.setdefault(GENERAL, {"slug": GENERAL, "label": "General visitor",
                             "description": "No clear goal yet; a broad introduction.",
                             "stage": "learn", "rules": {}, "priority": -100})
    return list(out.values())
