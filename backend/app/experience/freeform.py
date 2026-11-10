"""
Free-form pages, G3 (Phase 4, strategy §4.14).

A free-form route composes a page **per person and moment**:

    stable?    the visitor's page for this route, goal, taste and content → serve it
    assemble   pick the best cached fragments for the visitor's conditions (no model)
    compose    the model builds from fragments + components (within the budget),
               writing only the glue and new regions; new regions become fragments
    fallback   the G2 page (cached family plan → canonical) when nothing else fits

Governance: free-form only on routes set to it and not matching the blocked
patterns; pinned regions inserted unchanged; a share of served pages (and every
flagged one) goes to the review feed; crawlers never get G3.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import math
import random
import time
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experience import regions_store as rs
from app.experience.intent import Intent, Signals
from app.experience.manifest import ComponentManifest
from app.experience.plan import slug, validate_plan
from app.experience.routes_store import PAGE_REGIONS, Route

logger = logging.getLogger(__name__)

G3_REGIONS = "@g3"
PURPOSE_ORDER = ["hero", "intro", "highlights", "plans", "proof", "compare", "steps", "faq", "questions", "next", "cta"]
MIN_ASSEMBLED = 3
MAX_REGIONS = 8
DEFAULT_BLOCKED = ["/checkout*", "/cart*", "/legal*", "/terms*", "/privacy*"]
_SETTINGS = ("freeform_enabled", "g3_daily_budget", "g3_visitor_budget", "review_sample_pct", "g3_blocked_patterns")


# ---- settings -------------------------------------------------------------------

async def settings(db: AsyncSession, site_key: str) -> dict[str, Any]:
    r = (await db.execute(text(f"SELECT {', '.join(_SETTINGS)} FROM site_experience WHERE site_key = :sk"),
                          {"sk": site_key})).first()
    if r is None:
        return {"freeform_enabled": True, "g3_daily_budget": 200, "g3_visitor_budget": 3,
                "review_sample_pct": 5, "g3_blocked_patterns": list(DEFAULT_BLOCKED)}
    return {"freeform_enabled": bool(r.freeform_enabled), "g3_daily_budget": int(r.g3_daily_budget),
            "g3_visitor_budget": int(r.g3_visitor_budget), "review_sample_pct": int(r.review_sample_pct),
            "g3_blocked_patterns": list(r.g3_blocked_patterns or [])}


async def set_settings(db: AsyncSession, site_key: str, patch: dict[str, Any]) -> dict[str, Any]:
    cur = await settings(db, site_key)
    cur.update({k: v for k, v in patch.items() if k in _SETTINGS and v is not None})
    await db.execute(text("""
        INSERT INTO site_experience (site_key, freeform_enabled, g3_daily_budget, g3_visitor_budget,
            review_sample_pct, g3_blocked_patterns)
        VALUES (:sk, :fe, :db, :vb, :rp, :bp)
        ON CONFLICT (site_key) DO UPDATE SET freeform_enabled = EXCLUDED.freeform_enabled,
            g3_daily_budget = EXCLUDED.g3_daily_budget, g3_visitor_budget = EXCLUDED.g3_visitor_budget,
            review_sample_pct = EXCLUDED.review_sample_pct, g3_blocked_patterns = EXCLUDED.g3_blocked_patterns,
            updated_at = now()
    """), {"sk": site_key, "fe": cur["freeform_enabled"], "db": cur["g3_daily_budget"],
           "vb": cur["g3_visitor_budget"], "rp": cur["review_sample_pct"], "bp": cur["g3_blocked_patterns"]})
    await db.commit()
    return await settings(db, site_key)


def blocked_route(pattern: str, blocked: list[str]) -> Optional[str]:
    """The blocked pattern a route falls under (it may never be free-form)."""
    probe = pattern.replace("/*", "/x").replace(":", "")
    for b in blocked:
        if fnmatch.fnmatchcase(probe, b) or fnmatch.fnmatchcase(pattern, b):
            return b
    return None


# ---- budget --------------------------------------------------------------------------

async def budget_left(db: AsyncSession, site_key: str, visitor: str, cfg: dict[str, Any]) -> bool:
    r = (await db.execute(text(
        "SELECT COALESCE(sum(fresh), 0) AS site_n, COALESCE(sum(fresh) FILTER (WHERE visitor = :v), 0) AS v_n "
        "FROM g3_usage WHERE site_key = :sk AND day = current_date"), {"sk": site_key, "v": visitor})).first()
    return int(r.site_n) < cfg["g3_daily_budget"] and int(r.v_n) < cfg["g3_visitor_budget"]


async def spend(db: AsyncSession, site_key: str, visitor: str) -> None:
    await db.execute(text("""
        INSERT INTO g3_usage (site_key, day, visitor, fresh) VALUES (:sk, current_date, :v, 1)
        ON CONFLICT (site_key, day, visitor) DO UPDATE SET fresh = g3_usage.fresh + 1
    """), {"sk": site_key, "v": visitor})
    await db.commit()


# ---- fragments ---------------------------------------------------------------------------

def fingerprint(region: dict[str, Any]) -> str:
    raw = json.dumps({"c": region.get("component"), "p": region.get("props") or {}}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _frag_row(r: Any) -> dict[str, Any]:
    m = dict(r._mapping)
    m["id"] = str(m["id"])
    for k in ("created_at", "last_hit_at"):
        if m.get(k) is not None:
            m[k] = m[k].isoformat()
    return m


_FRAG_COLS = ("id, purpose, component, region, conditions, content_version, manifest_version, status, source, "
              "hit_count, rewards, created_at, last_hit_at")


async def store_fragments(db: AsyncSession, site_key: str, regions: list[dict[str, Any]], *, conditions: dict[str, Any],
                          content: str, manifest_version: Optional[int], source: str = "model") -> list[str]:
    ids = []
    for r in regions:
        fp = fingerprint(r)
        fid = uuid.uuid4()
        row = (await db.execute(text("""
            INSERT INTO fragment_cache (id, site_key, fingerprint, purpose, component, region, conditions,
                content_version, manifest_version, source)
            VALUES (:id, :sk, :fp, :pu, :c, CAST(:r AS jsonb), CAST(:co AS jsonb), :cv, :mv, :src)
            ON CONFLICT (site_key, fingerprint) DO UPDATE SET content_version = EXCLUDED.content_version
            RETURNING id
        """), {"id": fid, "sk": site_key, "fp": fp, "pu": slug(r.get("id")) or "region", "c": r.get("component"),
               "r": json.dumps({k: v for k, v in r.items() if k in ("id", "component", "props", "width")}),
               "co": json.dumps(conditions), "cv": content, "mv": manifest_version, "src": source})).first()
        ids.append(str(row.id))
    await db.commit()
    return ids


async def list_fragments(db: AsyncSession, site_key: str, *, status: Optional[str] = None, limit: int = 200
                         ) -> list[dict[str, Any]]:
    where = "site_key = :sk" + (" AND status = :st" if status else "")
    rows = (await db.execute(text(
        f"SELECT {_FRAG_COLS} FROM fragment_cache WHERE {where} "
        "ORDER BY (status = 'pinned') DESC, rewards DESC, hit_count DESC, created_at DESC LIMIT :lim"),
        {"sk": site_key, "st": status, "lim": max(1, min(limit, 500))})).all()
    return [_frag_row(r) for r in rows]


async def set_fragment_status(db: AsyncSession, site_key: str, fid: str, status: str) -> bool:
    if status not in ("auto", "pinned", "blocked"):
        return False
    try:
        u = uuid.UUID(fid)
    except ValueError:
        return False
    res = await db.execute(text("UPDATE fragment_cache SET status = :st WHERE site_key = :sk AND id = :id"),
                           {"st": status, "sk": site_key, "id": u})
    await db.commit()
    return (res.rowcount or 0) > 0


def score(f: dict[str, Any], intent: Intent, bucket: str, lang: str) -> float:
    c = f.get("conditions") or {}
    s = 0.0
    if f["status"] == "pinned":
        s += 10
    if c.get("family") == intent.family:
        s += 2
    elif c.get("family") not in (None, "", "general"):
        return -1  # written for another goal
    if c.get("lang", "en") != lang:
        return -1
    if bucket and c.get("taste") == bucket:
        s += 1
    hits = int(f.get("hit_count") or 0)
    if hits:
        s += 5 * int(f.get("rewards") or 0) / hits + math.log1p(hits) / 4
    return s


async def matching_fragments(db: AsyncSession, site_key: str, intent: Intent, *, bucket: str, lang: str,
                             content: str, manifest: ComponentManifest) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        f"SELECT {_FRAG_COLS} FROM fragment_cache WHERE site_key = :sk AND status <> 'blocked' "
        "AND (content_version = :cv OR status = 'pinned') ORDER BY created_at DESC LIMIT 400"),
        {"sk": site_key, "cv": content})).all()
    frags = [_frag_row(r) for r in rows]
    frags = [f for f in frags if manifest.get(f["component"]) is not None]
    scored = [(score(f, intent, bucket, lang), f) for f in frags]
    return [f for s, f in sorted(scored, key=lambda x: -x[0]) if s >= 0]


def assemble(frags: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """The best fragment per purpose, in page order. Returns (regions, fragment ids)."""
    best: dict[str, dict[str, Any]] = {}
    for f in frags:  # already best-first
        best.setdefault(f["purpose"], f)
    order = {p: i for i, p in enumerate(PURPOSE_ORDER)}
    chosen = sorted(best.values(), key=lambda f: order.get(f["purpose"], len(order)))[:MAX_REGIONS]
    regions = []
    for f in chosen:
        r = dict(f["region"])
        r["id"] = f["purpose"]
        regions.append(r)
    return regions, [f["id"] for f in chosen]


# ---- pinned regions and review flags ----------------------------------------------

def apply_pinned(regions: list[dict[str, Any]], pinned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {slug(p.get("id")) for p in pinned}
    rest = [r for r in regions if slug(r.get("id")) not in ids]
    top = [{k: v for k, v in p.items() if k != "position"} for p in pinned if p.get("position") != "bottom"]
    bottom = [{k: v for k, v in p.items() if k != "position"} for p in pinned if p.get("position") == "bottom"]
    return top + rest + bottom


def flags_for(report: Any, manifest: ComponentManifest, pinned: list[dict[str, Any]], dropped: list[str]) -> list[str]:
    out = []
    if report.problems or report.dropped or dropped:
        out.append("validator")
    if len(report.plan.regions) < MIN_ASSEMBLED:
        out.append("few regions")
    renderers = {manifest.get(r.component).renderer for r in report.plan.regions if manifest.get(r.component)}
    if not (renderers & {"cta", "enquiry_form"}) and not any("action" in r.props for r in report.plan.regions):
        out.append("no call to action")
    ids = {r.id for r in report.plan.regions}
    if any(slug(p.get("id")) not in ids for p in pinned):
        out.append("pinned region missing")
    return out


async def sample_for_review(db: AsyncSession, site_key: str, route: Route, plan_row: Optional[str],
                            plan: dict[str, Any], flags: list[str], pct: int) -> bool:
    if not flags and random.random() * 100 >= pct:
        return False
    await db.execute(text("""
        INSERT INTO review_samples (id, site_key, route, plan_row, plan, flags)
        VALUES (:id, :sk, :route, :pr, CAST(:plan AS jsonb), :flags)
    """), {"id": uuid.uuid4(), "sk": site_key, "route": route.pattern,
           "pr": uuid.UUID(plan_row) if plan_row else None, "plan": json.dumps(plan), "flags": flags})
    await db.commit()
    return True


async def list_reviews(db: AsyncSession, site_key: str, status: Optional[str] = None) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT id, route, plan_row, plan, flags, status, created_at, reviewed_by FROM review_samples "
        "WHERE site_key = :sk" + (" AND status = :st" if status else "") + " ORDER BY created_at DESC LIMIT 100"),
        {"sk": site_key, "st": status})).all()
    return [{"id": str(r.id), "route": r.route, "plan_row": str(r.plan_row) if r.plan_row else None, "plan": r.plan,
             "flags": list(r.flags or []), "status": r.status, "created_at": r.created_at.isoformat(),
             "reviewed_by": r.reviewed_by} for r in rows]


async def review(db: AsyncSession, site_key: str, rid: str, verdict: str, actor: Optional[str]) -> Optional[dict[str, Any]]:
    """OK, or flag: flagging blocks the page and the fragments it was assembled from."""
    try:
        u = uuid.UUID(rid)
    except ValueError:
        return None
    row = (await db.execute(text("SELECT plan_row, plan FROM review_samples WHERE site_key = :sk AND id = :id"),
                            {"sk": site_key, "id": u})).first()
    if row is None or verdict not in ("ok", "flagged"):
        return None
    await db.execute(text("UPDATE review_samples SET status = :st, reviewed_by = :by WHERE id = :id"),
                     {"st": verdict, "by": actor, "id": u})
    if verdict == "flagged":
        if row.plan_row:
            await rs.set_plan_status(db, site_key, str(row.plan_row), "blocked")
        for fid in ((row.plan or {}).get("provenance") or {}).get("fragments") or []:
            await set_fragment_status(db, site_key, fid, "blocked")
    await db.commit()
    return {"id": rid, "status": verdict}


# ---- experiment arm ----------------------------------------------------------------------

async def arm_allows(db: AsyncSession, site_key: str, visitor: str) -> bool:
    """False when a free-form test puts this visitor in the arm without free-form."""
    from app.experiments import store as exp_store

    exp = await exp_store.current(db, site_key)
    if exp is None or not exp.running or exp.subject != "freeform":
        return True
    got = await exp_store.enroll(db, site_key, visitor)
    if got is None or got["arm"] == "holdout":
        return False
    return got["overrides"].get("freeform") is not False


# ---- the model composer ------------------------------------------------------------------

G3_PROMPT = """You compose a page for ONE visitor from a business website's own building blocks.

Reuse FRAGMENTS where they fit ({"use": "F2"} places one unchanged); write new regions only
where the visitor needs something the fragments don't cover. Rules:
- Use ONLY facts from SOURCES or bound data; cite source ids; never invent numbers or claims.
- Live data comes from bindings ({"bind": "entity:<Type>"} or {"bind": "api:<op>"}), never typed.
- 4-8 regions. A region may be "width": "half" to sit beside the next half-width region.
- For a task that has steps (compare, then configure, then book) add "flow": [{"step", "title",
  "regions": [region ids]}] with 2-5 steps; otherwise leave flow out.
Call compose_page once."""


def _tool() -> Any:
    from app.ai.base import ToolSpec

    region = {"type": "object", "properties": {
        "use": {"type": "string"}, "id": {"type": "string"}, "component": {"type": "string"},
        "props": {"type": "object"}, "width": {"type": "string", "enum": ["full", "half"]},
        "sources": {"type": "array", "items": {"type": "string"}}}}
    return ToolSpec(name="compose_page", description="The visitor's page.", parameters={
        "type": "object", "properties": {
            "title": {"type": "string"}, "layout": {"type": "string", "enum": ["stack", "split"]},
            "regions": {"type": "array", "items": region},
            "flow": {"type": "array", "items": {"type": "object", "properties": {
                "step": {"type": "string"}, "title": {"type": "string"},
                "regions": {"type": "array", "items": {"type": "string"}}}}}},
        "required": ["title", "regions"]})


def _fragment_lines(frags: list[dict[str, Any]]) -> tuple[str, dict[str, dict[str, Any]]]:
    by_ref: dict[str, dict[str, Any]] = {}
    lines = []
    for i, f in enumerate(frags[:16], start=1):
        ref = f"F{i}"
        by_ref[ref] = f
        props = f["region"].get("props") or {}
        gist = "; ".join(f"{k}={str(v)[:50]!r}" for k, v in list(props.items())[:3] if not isinstance(v, (dict, list)))
        lines.append(f"[{ref}] purpose {f['purpose']}, {f['component']}: {gist}")
    return "\n".join(lines), by_ref


async def compose(db: AsyncSession, rt: Any, site_key: str, route: Route, params: dict[str, str], intent: Intent,
                  sig: Signals, *, manifest: ComponentManifest, registry: Any, llm: Any, model: Optional[str],
                  frags: list[dict[str, Any]], taste: Any = None, bindable: str = "", brand_voice: str = ""
                  ) -> Optional[dict[str, Any]]:
    """One model composition (plus one repair round). Returns
    ``{plan_raw, new_regions, used_fragments, tokens, dropped}`` or None."""
    from app.ai.base import ChatMessage
    from app.experience.page_planner import _prompt as page_prompt, candidates, check, entity_samples
    from app.experience.planner import gather

    focus = Signals(page=route.pattern, query=f"{route.title} {route.purpose}".strip(), lang=sig.lang)
    m = await gather(db, rt.bridge(db, site_key=site_key), site_key, intent, focus,
                     threshold=rt.settings.cortex_confidence_threshold)
    prefer = taste.value("format") if taste is not None else None
    cands = candidates(manifest, f"{intent.label} {intent.stage} {route.title} {route.purpose}", prefer)
    frag_text, by_ref = _fragment_lines(frags)
    base = page_prompt(route, params, intent, cands, m, await entity_samples(db, site_key), [], bindable=bindable,
                       brand_voice=brand_voice, taste_brief=taste.brief() if taste is not None else "")
    prompt = base + ("\nFRAGMENTS (reuse with {\"use\": \"F#\"}):\n" + frag_text if frag_text else "")
    allowed = {e.id for e in cands} | {f["component"] for f in frags}
    tokens = [0, 0]
    attempt_text = prompt
    for attempt in range(2):
        try:
            resp = await llm.generate(system=G3_PROMPT, messages=[ChatMessage(role="user", text=attempt_text)],
                                      tools=[_tool()], model=model, temperature=0.4, max_output_tokens=4000)
        except Exception as exc:
            logger.warning("free-form composition failed: %s", exc)
            return None
        tokens[0] += resp.input_tokens
        tokens[1] += resp.output_tokens
        call = next((tc for tc in resp.tool_calls if tc.name == "compose_page"), None)
        if call is None:
            return None
        regions, new_regions, used, problems = [], [], [], []
        for r in call.args.get("regions") or []:
            if not isinstance(r, dict):
                continue
            if r.get("use") in by_ref:
                f = by_ref[r["use"]]
                reg = {**f["region"], "id": f["purpose"]}
                if r.get("width") == "half":
                    reg["width"] = "half"
                regions.append(reg)
                used.append(f["id"])
            elif r.get("use"):
                problems.append(f"unknown fragment {r['use']!r}")
            else:
                new_regions.append({"id": str(r.get("id") or ""), "component": str(r.get("component") or ""),
                                    "props": r.get("props") if isinstance(r.get("props"), dict) else {},
                                    **({"width": "half"} if r.get("width") == "half" else {})})
                regions.append(new_regions[-1])
        checked_new, dropped = check(new_regions, allowed, m)
        checked = {c["id"]: c for c in checked_new}
        # New regions that failed the checks are left out; fragments stay as they were.
        final = [checked[r["id"]] if any(r is n for n in new_regions) else r
                 for r in regions if not any(r is n for n in new_regions) or r["id"] in checked]
        raw = {"title": str(call.args.get("title") or route.title or intent.label), "regions": final,
               "layout": call.args.get("layout") or "", "flow": call.args.get("flow"), "intent": intent.to_dict()}
        rep = validate_plan(raw, manifest=manifest, catalogue=registry, site_key=site_key)
        issues = problems + dropped + rep.problems + rep.dropped
        if len(rep.plan.regions) >= MIN_ASSEMBLED and not issues:
            return {"plan_raw": raw, "new_regions": checked_new, "used": used, "tokens": tokens, "dropped": []}
        if attempt == 0:
            attempt_text = (prompt + "\n\nYOUR PREVIOUS PAGE HAD THESE PROBLEMS — fix them:\n- " +
                            "\n- ".join(issues[:15]) + "\nPREVIOUS: " + json.dumps(call.args)[:6000])
        elif len(rep.plan.regions) >= MIN_ASSEMBLED:
            return {"plan_raw": raw, "new_regions": checked_new, "used": used, "tokens": tokens, "dropped": issues}
    return None


# ---- serving --------------------------------------------------------------------------------

def visitor_key(*, site_key: str, route: Route, params: dict[str, str], visitor: str, intent: Intent, sig: Signals,
                bucket: str, content: str, manifest_version: Optional[int]) -> str:
    who = "v:" + hashlib.sha256(f"{site_key}:{visitor}".encode()).hexdigest()[:20]
    return rs.plan_cache_key(family=intent.family, persona=who, lang=sig.lang,
                             page=route.pattern + "|" + json.dumps(params, sort_keys=True),
                             regions=[G3_REGIONS], content_version=content, manifest_version=manifest_version,
                             taste=bucket)


async def finalize_and_store(db: AsyncSession, site_key: str, route: Route, raw: dict[str, Any], *, key: str,
                             intent: Intent, sig: Signals, taste: Any, content: str, manifest: ComponentManifest,
                             registry: Any, composer: str, fragments: list[str], dropped: list[str], cfg: dict[str, Any],
                             build_ms: int) -> dict[str, Any]:
    pinned = [p for p in (await _pinned(db, site_key, route)) if isinstance(p, dict)]
    raw = {**raw, "regions": apply_pinned(list(raw.get("regions") or []), pinned),
           "provenance": {"source": "freeform", "composer": composer, "fragments": fragments,
                          "manifest": manifest.source, "manifest_version": manifest.version, "route": route.pattern}}
    report = validate_plan(raw, manifest=manifest, catalogue=registry, site_key=site_key)
    flags = flags_for(report, manifest, pinned, dropped)
    plan = report.plan.to_dict()
    row = await rs.store_plan(db, site_key, key=key, family=intent.family, persona="", lang=sig.lang,
                              page=route.pattern, regions=[G3_REGIONS], content_version=content,
                              manifest_version=manifest.version, plan=plan, composer=composer, build_ms=build_ms,
                              taste=taste.bucket() if taste is not None else "")
    await sample_for_review(db, site_key, route, row["id"], plan, flags, cfg["review_sample_pct"])
    row["flags"] = flags
    return row


async def _pinned(db: AsyncSession, site_key: str, route: Route) -> list[dict[str, Any]]:
    r = (await db.execute(text("SELECT pinned_regions FROM site_routes WHERE site_key = :sk AND pattern = :p"),
                          {"sk": site_key, "p": route.pattern})).first()
    return list(r.pinned_regions or []) if r else []


async def build_composed(db: AsyncSession, rt: Any, site_key: str, route: Route, params: dict[str, str],
                         intent: Intent, sig: Signals, *, key: str, visitor: str, taste: Any, content: str
                         ) -> Optional[dict[str, Any]]:
    """A model-composed page (counted against the budget); its new regions become fragments."""
    from app.apis.registry import get_site_apis
    from app.config import get_settings
    from app.design.system import ensure_design, load_design_system
    from app.experience.manifest import ensure_manifest, load_manifest
    from app.experience.regions import planner_llm
    from app.orchestrator.pagegen import bindable_prompt

    t0 = time.monotonic()
    await ensure_design(site_key)
    await ensure_manifest(site_key)
    manifest, registry = load_manifest(site_key), get_site_apis(site_key)
    cfg = await settings(db, site_key)
    llm = await planner_llm(db, rt, site_key)
    if llm is None or not await budget_left(db, site_key, visitor, cfg):
        return None
    await spend(db, site_key, visitor)
    bucket = taste.bucket() if taste is not None else ""
    frags = await matching_fragments(db, site_key, intent, bucket=bucket, lang=sig.lang, content=content,
                                     manifest=manifest)
    got = await compose(db, rt, site_key, route, params, intent, sig, manifest=manifest, registry=registry,
                        llm=llm, model=get_settings().heavy_model, frags=frags, taste=taste,
                        bindable=bindable_prompt(site_key), brand_voice=load_design_system(site_key).brand_voice)
    if got is None:
        return None
    new_ids = await store_fragments(db, site_key, got["new_regions"], conditions={
        "family": intent.family, "stage": intent.stage, "taste": bucket, "lang": sig.lang},
        content=content, manifest_version=manifest.version)
    return await finalize_and_store(db, site_key, route, got["plan_raw"], key=key, intent=intent, sig=sig,
                                    taste=taste, content=content, manifest=manifest, registry=registry,
                                    composer="model", fragments=got["used"] + new_ids, dropped=got["dropped"],
                                    cfg=cfg, build_ms=int((time.monotonic() - t0) * 1000))


async def serve_freeform(db: AsyncSession, rt: Any, site_key: str, route: Route, params: dict[str, str],
                         intent: Intent, sig: Signals, *, visitor: str, taste: Any, content: str,
                         manifest: ComponentManifest, wait: bool = False) -> Optional[dict[str, Any]]:
    """The visitor's G3 page row, or None (the caller serves the G2 page)."""
    from app.apis.registry import get_site_apis
    from app.experience.regions import _schedule

    cfg = await settings(db, site_key)
    if not cfg["freeform_enabled"] or blocked_route(route.pattern, cfg["g3_blocked_patterns"]):
        return None
    if not await arm_allows(db, site_key, visitor):
        return None
    bucket = taste.bucket() if taste is not None else ""
    key = visitor_key(site_key=site_key, route=route, params=params, visitor=visitor, intent=intent, sig=sig,
                      bucket=bucket, content=content, manifest_version=manifest.version)
    row = await rs.cached_plan(db, site_key, key)
    if row is not None:
        row["served"] = "stable"
        return row
    if wait:
        row = await build_composed(db, rt, site_key, route, params, intent, sig, key=key, visitor=visitor,
                                   taste=taste, content=content)
        if row is not None:
            row["served"] = "composed"
            return row
    frags = await matching_fragments(db, site_key, intent, bucket=bucket, lang=sig.lang, content=content,
                                     manifest=manifest)
    regions, used = assemble(frags)
    if len(regions) < MIN_ASSEMBLED and await seed_from_route(db, site_key, route, content=content,
                                                              manifest_version=manifest.version):
        frags = await matching_fragments(db, site_key, intent, bucket=bucket, lang=sig.lang, content=content,
                                         manifest=manifest)
        regions, used = assemble(frags)
    if len(regions) >= MIN_ASSEMBLED:
        row = await finalize_and_store(db, site_key, route, {"title": route.title or intent.label, "regions": regions,
                                                             "intent": intent.to_dict()},
                                       key=key, intent=intent, sig=sig, taste=taste, content=content,
                                       manifest=manifest, registry=get_site_apis(site_key), composer="assembled",
                                       fragments=used, dropped=[], cfg=cfg, build_ms=0)
        if used:
            await db.execute(text("UPDATE fragment_cache SET hit_count = hit_count + 1, last_hit_at = now() "
                                  "WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": used})
            await db.commit()
        row["served"] = "assembled"
        return row

    # Not enough fragments yet: compose one in the background for next time.
    async def build() -> None:
        from app.db import session_scope

        async with session_scope() as bdb:
            await build_composed(bdb, rt, site_key, route, params, intent, sig, key=key, visitor=visitor,
                                 taste=taste, content=content)

    _schedule(f"{site_key}:{key}", build)
    return None


def seed_fragments_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Regions of a G2 plan as fragments (so free-form routes start with material)."""
    return [r for r in (plan.get("regions") or []) if isinstance(r, dict) and r.get("component")]


async def seed_from_route(db: AsyncSession, site_key: str, route: Route, *, content: str,
                          manifest_version: Optional[int]) -> int:
    """Seed fragments from the route's existing composed pages: a route switched to
    free-form after it already had pages starts with material at once. Pinned pages
    (the owner chose them) count whatever their content version; others only when
    built from the current content. Returns how many fragments were stored."""
    rows = (await db.execute(text(
        "SELECT plan, family, lang, composer FROM plan_cache WHERE site_key = :sk AND page = :p AND regions = :r "
        "AND status <> 'blocked' AND (status = 'pinned' OR content_version = :cv) "
        "ORDER BY (status = 'pinned') DESC, hit_count DESC, created_at DESC LIMIT 5"),
        {"sk": site_key, "p": route.pattern, "r": PAGE_REGIONS, "cv": content})).all()
    n = 0
    for r in rows:
        regions = seed_fragments_from_plan(r.plan or {})
        if regions:
            n += len(await store_fragments(db, site_key, regions, conditions={"family": r.family, "lang": r.lang},
                                           content=content, manifest_version=manifest_version,
                                           source=r.composer or "rules"))
    return n

