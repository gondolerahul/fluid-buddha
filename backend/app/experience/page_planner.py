"""
G2 page planner (P2-3): compose a whole page for a route and an intent family.

    material (CORTEX for the route's purpose and the intent, pinned answers)
    + the manifest components most relevant to them (≤ 16)
    + the entity types the page can bind, with a sample of their fields
    + up to 3 exemplar outlines (pinned / most-served page plans of the family)
      → the model composes the page (a tool call over the manifest)
      → checks: allowed components, numbers backed by material, the shared
        plan validator
      → one repair round with the problems, if any
      → fallbacks: the nearest cached plan for the route → the route's
        canonical plan → a rules page (hero, intro, highlights, FAQ, CTA)
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experience.intent import Intent, Signals
from app.experience.manifest import ComponentManifest, ManifestEntry
from app.experience.plan import validate_plan
from app.experience.planner import Material, _numbers_ok, compose_rules, gather
from app.experience.regions_store import RegionSlot
from app.experience.routes_store import PAGE_REGIONS, Route

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 16
ALWAYS = ("fb.hero", "fb.text", "fb.cta")
_WORD_RE = re.compile(r"[a-z0-9]+")

PAGE_PROMPT = """You compose a whole web page for a business website from its own components.

The visitor's likely goal is the INTENT; the page is the ROUTE. Build 4-8 regions, in order,
using ONLY the listed components and their props. Rules:
- Use ONLY facts from SOURCES or bound data. Cite source ids in "sources".
- Never invent numbers, prices, customers or claims. Any number you write must appear in a source.
- Live data and records come from bindings, never typed: {"bind": "api:<op>"} or
  {"bind": "entity:<Type>", "params": {"key": "route.slug"}} or {"bind": "entity:<Type>", "params": {"limit": 6}}.
  When record fields differ from a prop's shape, rename them: "map": {"title": "name", "body": "summary"}.
- Props marked model_text are short copy you write; binding_only props must be bindings.
- Give each region a short, stable id (hero, plans, proof, faq, next...).
Call compose_page once."""

RULES_SLOTS = [
    RegionSlot(id="r1", name="hero", components=["fb.hero"]),
    RegionSlot(id="r2", name="intro", components=["fb.text"]),
    RegionSlot(id="r3", name="highlights", components=["fb.feature_grid"]),
    RegionSlot(id="r4", name="questions", components=["fb.faq"]),
    RegionSlot(id="r5", name="next", label="Talk to us", components=["fb.cta"]),
]


def _words(s: str) -> set[str]:
    return {w for w in _WORD_RE.findall((s or "").lower()) if len(w) > 2}


def candidates(manifest: ComponentManifest, focus: str, prefer: Optional[str] = None) -> list[ManifestEntry]:
    """The components most relevant to the route and intent (always the basics);
    components suiting the visitor's format preference rank higher (Phase 3)."""
    from app.experience.planner import FORMAT_RENDERERS

    fw = _words(focus)
    good = FORMAT_RENDERERS.get(prefer or "", ())
    scored = []
    for e in manifest.entries():
        hay = _words(" ".join([e.purpose, e.id.replace(".", " "), *e.use_when]))
        bonus = 1 if not e.id.startswith("fb.") else 0  # prefer the customer's own components
        bonus += 2 if e.renderer in good else 0
        scored.append((len(hay & fw) + bonus, e))
    scored.sort(key=lambda x: -x[0])
    picked = [e for _, e in scored[:MAX_CANDIDATES]]
    for cid in ALWAYS:
        e = manifest.get(cid)
        if e and e not in picked:
            picked.append(e)
    return picked


async def entity_samples(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT DISTINCT ON (type) type, key, data, (SELECT count(*) FROM site_entities s2 "
        "WHERE s2.site_key = s.site_key AND s2.type = s.type) AS n "
        "FROM site_entities s WHERE site_key = :sk ORDER BY type, key LIMIT 20"), {"sk": site_key})).all()
    return [{"type": r.type, "count": r.n, "sample_key": r.key,
             "fields": sorted(list((r.data or {}).keys()))[:15]} for r in rows]


async def exemplars(db: AsyncSession, site_key: str, family: str, limit: int = 3) -> list[list[str]]:
    rows = (await db.execute(text(
        "SELECT plan FROM plan_cache WHERE site_key = :sk AND regions = :r AND family = :f AND status <> 'blocked' "
        "ORDER BY (status = 'pinned') DESC, hit_count DESC LIMIT :n"),
        {"sk": site_key, "r": PAGE_REGIONS, "f": family, "n": limit})).all()
    out = []
    for (plan,) in rows:
        regs = (plan or {}).get("regions") or []
        out.append([f"{r.get('id')}:{r.get('component')}" for r in regs if isinstance(r, dict)])
    return out


def _tool_spec() -> Any:
    from app.ai.base import ToolSpec

    return ToolSpec(name="compose_page", description="The composed page.", parameters={
        "type": "object", "properties": {
            "title": {"type": "string"},
            "regions": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"}, "component": {"type": "string"}, "props": {"type": "object"},
                "sources": {"type": "array", "items": {"type": "string"}}},
                "required": ["id", "component", "props"]}}},
        "required": ["title", "regions"]})


def _prompt(route: Route, params: dict[str, str], intent: Intent, cands: list[ManifestEntry], m: Material,
            ents: list[dict[str, Any]], examples: list[list[str]], *, bindable: str, brand_voice: str,
            taste_brief: str = "", avoid: str = "") -> str:
    lines = [f"ROUTE: {route.pattern} — {route.title or ''}. Purpose: {route.purpose or 'a page of the site'}",
             f"VISITOR TASTE: {taste_brief}" if taste_brief else "",
             f"VARIANT: take a clearly different angle from this version: {avoid}" if avoid else "",
             f"ROUTE PARAMETERS: {json.dumps(params)}" if params else "",
             f"INTENT: {intent.label} (stage: {intent.stage or 'unknown'})",
             f"BRAND VOICE: {brand_voice}" if brand_voice else "",
             "COMPONENTS: " + "; ".join(e.to_prompt() for e in cands)]
    if ents:
        lines.append("ENTITIES (bind with entity:<Type>): " + "; ".join(
            f"{e['type']} ({e['count']} records, fields: {', '.join(e['fields'])}, e.g. key {e['sample_key']})"
            for e in ents))
    if bindable:
        lines.append(bindable)
    if examples:
        lines.append("PAGES THAT WORKED FOR THIS GOAL (outlines): " + " | ".join(" > ".join(x) for x in examples))
    lines.append("SOURCES:")
    lines += [f"[{k}] {s['text']}" for k, s in m.sources.items()]
    if m.golden:
        lines.append("APPROVED ANSWERS:")
        lines += [f"Q: {q} A: {a}" for q, a in m.golden]
    return "\n".join(x for x in lines if x)


def _regions_from_call(call: Any) -> tuple[str, list[dict[str, Any]]]:
    regs = []
    for r in call.args.get("regions") or []:
        if isinstance(r, dict):
            regs.append({"id": str(r.get("id") or ""), "component": str(r.get("component") or ""),
                         "props": r.get("props") if isinstance(r.get("props"), dict) else {}})
    return str(call.args.get("title") or ""), regs


def check(regions: list[dict[str, Any]], allowed: set[str], m: Material) -> tuple[list[dict[str, Any]], list[str]]:
    """Allowed components and numbers backed by material."""
    text_ = m.all_text()
    out, dropped = [], []
    for r in regions:
        if r["component"] not in allowed:
            dropped.append(f"{r['id'] or '?'}: component {r['component']!r} is not available")
            continue
        props = {}
        for k, v in r["props"].items():
            if _numbers_ok(v, text_):
                props[k] = v
            else:
                dropped.append(f"{r['id']}.{k}: a number not found in the site's content")
        out.append({**r, "props": props})
    return out, dropped


async def build_page_plan(
    db: AsyncSession, rt: Any, site_key: str, route: Route, params: dict[str, str], intent: Intent,
    sig: Signals, *, manifest: ComponentManifest, registry: Any, llm: Any = None, model: Optional[str] = None,
    bindable: str = "", brand_voice: str = "", taste: Any = None, variant: int = 0, avoid: str = "",
) -> dict[str, Any]:
    """``{plan, composer, build_ms, tokens, dropped, problems}``."""
    t0 = time.monotonic()
    bridge = rt.bridge(db, site_key=site_key)
    focus_sig = Signals(page=route.pattern, query=f"{route.title} {route.purpose}".strip(), lang=sig.lang)
    m = await gather(db, bridge, site_key, intent, focus_sig, threshold=rt.settings.cortex_confidence_threshold)
    prefer = taste.value("format") if taste is not None else None
    taste_brief = taste.brief() if taste is not None else ""
    cands = candidates(manifest, f"{intent.label} {intent.stage} {route.title} {route.purpose}", prefer)
    allowed = {e.id for e in cands}
    tokens = [0, 0]
    dropped: list[str] = []

    def finish(title: str, regions: list[dict[str, Any]], composer: str) -> Any:
        rep = validate_plan({"title": title or route.title or intent.label, "regions": regions,
                             "intent": intent.to_dict(),
                             "provenance": {"source": "page_planner", "composer": composer,
                                            "manifest": manifest.source, "manifest_version": manifest.version,
                                            "route": route.pattern}},
                            manifest=manifest, catalogue=registry, site_key=site_key)
        return rep

    if llm is not None:
        from app.ai.base import ChatMessage

        ents = await entity_samples(db, site_key)
        ex = await exemplars(db, site_key, intent.family)
        prompt = _prompt(route, params, intent, cands, m, ents, ex, bindable=bindable, brand_voice=brand_voice,
                         taste_brief=taste_brief, avoid=avoid)
        attempt_text = prompt
        for attempt in range(2):  # the first try, then one repair round
            try:
                resp = await llm.generate(system=PAGE_PROMPT, messages=[ChatMessage(role="user", text=attempt_text)],
                                          tools=[_tool_spec()], model=model, temperature=0.3,
                                          max_output_tokens=4000)
            except Exception as exc:
                logger.warning("page planning failed: %s", exc)
                break
            tokens[0] += resp.input_tokens
            tokens[1] += resp.output_tokens
            call = next((tc for tc in resp.tool_calls if tc.name == "compose_page"), None)
            if call is None:
                break
            title, raw = _regions_from_call(call)
            regions, d1 = check(raw, allowed, m)
            rep = finish(title, regions, "model" if attempt == 0 else "repaired")
            issues = d1 + rep.dropped + rep.problems
            if len(rep.plan.regions) >= 2 and not issues:
                return _out(rep, "model" if attempt == 0 else "repaired", t0, tokens, dropped)
            if attempt == 0:
                attempt_text = (prompt + "\n\nYOUR PREVIOUS PAGE HAD THESE PROBLEMS — fix them and call "
                                "compose_page again:\n- " + "\n- ".join(issues[:15]) +
                                "\nPREVIOUS PAGE: " + json.dumps({"title": title, "regions": raw})[:6000])
            elif len(rep.plan.regions) >= 2:
                dropped += issues
                return _out(rep, "repaired", t0, tokens, dropped)
            else:
                dropped += issues

    # Fallbacks: the nearest cached plan for this route, then its canonical plan.
    row = (await db.execute(text(
        "SELECT plan FROM plan_cache WHERE site_key = :sk AND regions = :r AND page = :p AND status <> 'blocked' "
        "ORDER BY (status = 'pinned') DESC, hit_count DESC, created_at DESC LIMIT 1"),
        {"sk": site_key, "r": PAGE_REGIONS, "p": route.pattern})).first()
    if row is None and route.canonical_plan:
        row = (await db.execute(text("SELECT plan FROM plan_cache WHERE id = CAST(:id AS uuid)"),
                                {"id": route.canonical_plan})).first()
    if row is not None and llm is not None:
        rep = validate_plan(row[0], manifest=manifest, catalogue=registry, site_key=site_key)
        if rep.plan.regions:
            rep.plan.provenance["composer"] = "fallback"
            return _out(rep, "fallback", t0, tokens, dropped)

    # The route's own title heads the rules page (not the intent's label).
    title = route.title or route.purpose or intent.label
    slots = [RegionSlot(id=s.id, name=s.name, label=title if s.name == "hero" else s.label,
                        components=s.components) for s in RULES_SLOTS]
    if variant % 2 == 1:  # a bandit arm: highlights before the intro
        slots[1], slots[2] = slots[2], slots[1]
    regions = compose_rules(slots, manifest, Intent("page", title, intent.stage) if intent.family == "general"
                            else intent, focus_sig, m, prefer=prefer,
                            short=taste is not None and taste.value("detail") == "summary")
    rep = finish(route.title or intent.label, regions, "rules")
    return _out(rep, "rules", t0, tokens, dropped)


def _out(rep: Any, composer: str, t0: float, tokens: list[int], dropped: list[str]) -> dict[str, Any]:
    rep.plan.provenance["composer"] = composer
    return {"plan": rep.plan.to_dict(), "composer": composer, "tokens": tokens,
            "build_ms": int((time.monotonic() - t0) * 1000), "dropped": dropped + rep.dropped,
            "problems": rep.problems}
