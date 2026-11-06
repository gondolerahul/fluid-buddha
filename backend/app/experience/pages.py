"""
Serving composed pages (Phase 2: P2-1, P2-3, P2-5).

``serve_page`` answers one request for a route:

    route match → ?fbv restore | crawler → canonical page | visitor → intent →
    pinned → cached → (miss: serve the best available page now, build the
    visitor's plan in the background) → bind live data → SSR fragment + head

A cache miss never waits for a model: the visitor gets the route's canonical
plan, else its most-served plan, else a rules page composed from site content
(no model, fast), and their own plan is ready for the next page view.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.experience import regions_store as rs
from app.experience import routes_store as routes
from app.experience.binding import bind_plan
from app.experience.intent import Intent, Signals
from app.experience.manifest import ensure_manifest, is_wc_renderer, load_manifest
from app.experience.plan import validate_plan
from app.experience.regions import _content_version, _schedule as _schedule_token, intent_for, pick_arm, planner_llm
from app.experience.resolvers import make_resolver
from app.experience.routes_store import PAGE_REGIONS, Route

logger = logging.getLogger(__name__)



async def plan_by_plan_id(db: AsyncSession, site_key: str, plan_id: str, *, page: Optional[str] = None
                          ) -> Optional[dict[str, Any]]:
    """A stored page plan by its ``plan_id`` (``?fbv=`` and patches)."""
    if not plan_id or not plan_id.startswith("pl_") or len(plan_id) > 20:
        return None
    sql = ("SELECT id FROM plan_cache WHERE site_key = :sk AND regions = :r AND status <> 'blocked' "
           "AND plan->>'plan_id' = :pid")
    params: dict[str, Any] = {"sk": site_key, "r": PAGE_REGIONS, "pid": plan_id}
    if page:
        sql += " AND page = :p"
        params["p"] = page
    row = (await db.execute(text(sql + " LIMIT 1"), params)).first()
    return await rs.get_plan(db, site_key, str(row.id)) if row else None


async def _best_for_route(db: AsyncSession, site_key: str, route: Route) -> Optional[dict[str, Any]]:
    if route.canonical_plan:
        row = await rs.get_plan(db, site_key, route.canonical_plan)
        if row and row["status"] != "blocked":
            return row
    r = (await db.execute(text(
        "SELECT id FROM plan_cache WHERE site_key = :sk AND regions = :r AND page = :p AND status <> 'blocked' "
        "ORDER BY (status = 'pinned') DESC, hit_count DESC, created_at DESC LIMIT 1"),
        {"sk": site_key, "r": PAGE_REGIONS, "p": route.pattern})).first()
    return await rs.get_plan(db, site_key, str(r.id)) if r else None


async def build_and_store_page(
    db: AsyncSession, rt: Any, site_key: str, route: Route, params: dict[str, str], intent: Intent,
    sig: Signals, *, key: str, content: str, use_model: bool = True, taste: Any = None, arm: int = 0,
    base_key: Optional[str] = None, avoid: str = "",
) -> dict[str, Any]:
    from app.apis.registry import get_site_apis
    from app.design.system import ensure_design, load_design_system
    from app.experience.page_planner import build_page_plan
    from app.orchestrator.pagegen import bindable_prompt

    await ensure_design(site_key)
    await ensure_manifest(site_key)
    manifest = load_manifest(site_key)
    llm = await planner_llm(db, rt, site_key) if use_model else None
    built = await build_page_plan(
        db, rt, site_key, route, params, intent, sig, manifest=manifest, registry=get_site_apis(site_key),
        llm=llm, model=get_settings().heavy_model, bindable=bindable_prompt(site_key),
        brand_voice=load_design_system(site_key).brand_voice, taste=taste, variant=arm, avoid=avoid)
    row = await rs.store_plan(
        db, site_key, key=key, family=intent.family, persona=sig.persona, lang=sig.lang, page=route.pattern,
        regions=[PAGE_REGIONS], content_version=content, manifest_version=manifest.version,
        plan=built["plan"], composer=built["composer"], build_ms=built["build_ms"],
        taste=taste.bucket() if taste is not None else "", arm=arm, base_key=base_key or key)
    row["dropped"], row["problems"] = built["dropped"], built["problems"]
    return row


def _schedule(rt: Any, site_key: str, route: Route, params: dict[str, str], intent: Intent, sig: Signals,
              *, key: str, content: str, taste: Any = None, arm: int = 0, base_key: Optional[str] = None,
              avoid: str = "") -> None:
    async def build() -> None:
        from app.db import session_scope

        async with session_scope() as db:
            await build_and_store_page(db, rt, site_key, route, params, intent, sig, key=key, content=content,
                                       taste=taste, arm=arm, base_key=base_key, avoid=avoid)

    _schedule_token(f"{site_key}:{key}", build)


async def bind_page(db: AsyncSession, rt: Any, site_key: str, plan: dict[str, Any], ctx: dict[str, Any]
                    ) -> tuple[list[dict[str, Any]], Any, str]:
    """Validate a stored plan against today's manifest and bind live data.
    Returns ``(sections in order, manifest, plan_id)``."""
    from app.apis.registry import get_site_apis

    manifest = load_manifest(site_key)
    registry = get_site_apis(site_key)
    report = validate_plan(plan, manifest=manifest, catalogue=registry, site_key=site_key)
    pid = plan.get("plan_id") or report.plan.plan_id
    report.plan.plan_id = pid
    bound = await bind_plan(report.plan, manifest=manifest, registry=registry, ctx=ctx,
                            resolve=make_resolver(db, rt, site_key))
    return [b.to_section() for b in bound if b.state == "ready"], manifest, pid


def _description(sections: list[dict[str, Any]]) -> str:
    for s in sections:
        p = s.get("props") or {}
        for k in ("subtitle", "body"):
            v = p.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()[:160]
    return ""


def canonical_url(domain: str, path: str) -> str:
    d = (domain or "").strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    return f"https://{d}{path}" if d else path


async def serve_page(
    db: AsyncSession, rt: Any, site_key: str, *, path: str, sig: Signals, fbv: Optional[str] = None,
    bot: bool = False, domain: str = "", api_base: str = "", public_key: str = "", wait: bool = False,
    taste: Any = None,
) -> dict[str, Any]:
    from app.design.system import ensure_design, load_design_system
    from app.experience.personal import apply_tunables, explain
    from app.experience.ssr import render_fragment, stylesheet
    from app.orchestrator.profile import profile_for

    path = rs.normalize_page(path)
    matched = await routes.match_route(db, site_key, path)
    if matched is None:
        return {"status": 404, "reason": "no_route"}
    route, params = matched
    await ensure_manifest(site_key)
    await ensure_design(site_key)
    out: dict[str, Any] = {"status": 200, "route": route.pattern, "params": params, "pending": False}

    row: Optional[dict[str, Any]] = None
    restored = False
    intent: Optional[Intent] = None
    if bot:
        taste = None  # crawlers get the brand's own page
    if fbv:
        row = await plan_by_plan_id(db, site_key, fbv, page=route.pattern)
        restored = row is not None
    if row is None and bot:
        row = await _best_for_route(db, site_key, route)
        out["served"] = "canonical" if row and row["id"] == route.canonical_plan else "best"
    if row is None:
        intent = (Intent() if bot else await intent_for(db, rt, site_key, sig))
        out["intent"] = intent.to_dict()
        manifest = load_manifest(site_key)
        content = await _content_version(db, site_key)
        key = rs.plan_cache_key(family=intent.family, persona=sig.persona, lang=sig.lang, page=route.pattern,
                                regions=[PAGE_REGIONS], content_version=content,
                                manifest_version=manifest.version,
                                taste=taste.bucket() if taste is not None else "")
        row = await rs.pinned_plan(db, site_key, family=intent.family, page=route.pattern, regions=[PAGE_REGIONS])
        out["served"] = "pinned" if row else "cached"
        if row is None:
            row = await pick_arm(db, site_key, key, on_new_arm=lambda n, avoid: _schedule(
                rt, site_key, route, params, intent, sig, key=f"{key}#arm{n}", content=content, taste=taste,
                arm=n, base_key=key, avoid=avoid))
        if row is None:
            if wait or bot:
                row = await build_and_store_page(db, rt, site_key, route, params, intent, sig, key=key,
                                                 content=content, use_model=not bot, taste=taste)
                out["served"] = "built"
            else:
                _schedule(rt, site_key, route, params, intent, sig, key=key, content=content, taste=taste)
                out["pending"] = True
                row = await _best_for_route(db, site_key, route)
                out["served"] = "fallback"
                if row is None:
                    # Nothing yet for this route at all: a rules page now (no model, fast).
                    row =await build_and_store_page(db, rt, site_key, route, params, Intent(), sig,
                                                     key=rs.plan_cache_key(
                                                         family="general", persona="", lang=sig.lang,
                                                         page=route.pattern, regions=[PAGE_REGIONS],
                                                         content_version=content,
                                                         manifest_version=manifest.version),
                                                     content=content, use_model=False)
    if row is None:
        return {"status": 404, "reason": "no_plan"}
    if not restored:
        await rs.record_hit(db, row["id"])

    ctx = {"site_key": site_key, "currency": profile_for(site_key).currency, "lang": sig.lang,
           "persona": sig.persona, "page": path, "route": params}
    sections, manifest, plan_id = await bind_page(db, rt, site_key, row["plan"], ctx)
    design = load_design_system(site_key)
    overrides, applied = apply_tunables(design, taste)
    why = explain(intent, sig, taste, served=out.get("served", ""), applied=applied)
    canonical = canonical_url(domain, path)
    is_canonical = bool(route.canonical_plan) and row["id"] == route.canonical_plan
    title = str(row["plan"].get("title") or route.title or design.name)
    desc = _description(sections)
    out.update({
        "plan_id": plan_id,
        "plan_row": row["id"],
        "html": render_fragment(sections, plan_id=plan_id, title=title,
                                form_action=f"{api_base.rstrip('/')}/experience/lead" if api_base else ""),
        "css": stylesheet(design, overrides),
        "why": why,
        "arm": row.get("arm", 0),
        "head": {
            "title": title, "description": desc, "canonical": canonical,
            # Crawlers and the owner's canonical page are indexed; generated variants aren't.
            "robots": "index, follow" if (bot or is_canonical) and not restored else "noindex, follow",
            "json_ld": {"@context": "https://schema.org", "@type": "WebPage", "name": title,
                        "description": desc, "url": canonical},
        },
        "data": {"plan_id": plan_id, "api": api_base, "key": public_key, "page": path, "why": why,
                 "sections": [s for s in sections if s["type"] in ("chart", "roi_calculator", "enquiry_form")
                              or is_wc_renderer(s["type"])]},
        "tokens": {**design.to_tokens(), **overrides},
        "restored": restored,
    })
    if manifest.bundle and any(is_wc_renderer(s["type"]) for s in sections):
        out["bundle"] = manifest.bundle
    return out
