"""
Serving generated regions (P1-1 / P1-3).

``serve_regions`` answers one page's request for its slots:

    switch off / bot / experiment arm without regions → nothing (the host's own
    content stays) → slots enabled for this page → intent → pinned plan →
    cached plan → bind live data → regions

On a cache miss nothing waits for a model: the plan is built in the
background (one build per cache key at a time) and the answer says
``pending`` so the widget can ask once more.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.experience import regions_store as rs
from app.experience.binding import bind_plan
from app.experience.intent import GENERAL, Intent, Signals, resolve_intent
from app.experience.manifest import ensure_manifest, is_wc_renderer, load_manifest
from app.experience.plan import validate_plan

logger = logging.getLogger(__name__)

RETRY_AFTER_MS = 2500
BUILDS_PER_MIN = 20
_building: set[str] = set()
_tasks: set[asyncio.Task] = set()


def _embedder(rt: Any):
    from cortex_memory.embedding import embed_query

    async def embed(text_: str) -> Optional[list[float]]:
        try:
            return await embed_query(rt.providers.embedding, text_)
        except Exception as exc:
            logger.debug("embedding failed: %s", exc)
            return None
    return embed


async def planner_llm(db: AsyncSession, rt: Any, site_key: str) -> Any:
    """The account's own model or the platform's, unless mock mode, the build
    rate or the daily spend cap says no (then the rules compose for free)."""
    from app.ai.providers import config_for_site, current_site
    from app.transport import guard

    settings = get_settings()
    if not guard._limiter.allow(f"region-build:{site_key}", BUILDS_PER_MIN):
        return None
    if await guard.check_public_budget(db, site_key, settings):
        return None
    current_site.set(site_key)
    byo = await config_for_site(site_key)
    return rt.engines.llm if (byo is not None or not settings.mock_ai) else None


def _classifier(rt: Any, llm: Any):
    """Background family classification with the fast model (P1-2 step 3)."""
    if llm is None:
        return None
    from app.ai.base import ChatMessage

    async def classify(families: list[rs.IntentFamily], sig: Signals) -> Optional[str]:
        listing = "\n".join(f"- {f.slug}: {f.label}. {f.description}" for f in families)
        resp = await llm.generate(
            system="Pick the visitor's most likely goal. Answer with ONLY one slug from the list, "
                   "or 'general' if none fits.",
            messages=[ChatMessage(role="user", text=f"GOALS:\n{listing}\n\nSIGNALS: page={sig.page} "
                                  f"campaign={sig.utm_campaign} source={sig.utm_source} "
                                  f"search={sig.query or sig.referrer_terms} referrer={sig.referrer_host}")],
            model=get_settings().fast_model, temperature=0.0, max_output_tokens=20)
        slug = (resp.text or "").strip().strip("`'\" .").lower()
        return slug or None
    return classify


async def intent_for(db: AsyncSession, rt: Any, site_key: str, sig: Signals, *,
                     background_model: bool = True) -> Intent:
    families = await rs.list_families(db, site_key)
    classify = None
    if background_model and families:
        settings = get_settings()
        if not settings.mock_ai:
            classify = _classifier(rt, rt.engines.llm)
    return await resolve_intent(site_key, families, sig, embed=_embedder(rt), classify=classify)


async def _content_version(db: AsyncSession, site_key: str) -> str:
    from app.campaigns.store import content_version

    return await content_version(db, site_key)


async def build_and_store(
    db: AsyncSession, rt: Any, site_key: str, slots: list[rs.RegionSlot], intent: Intent, sig: Signals,
    *, key: str, content: str, use_model: bool = True, taste: Any = None, arm: int = 0,
    base_key: Optional[str] = None, avoid: str = "",
) -> dict[str, Any]:
    from app.apis.registry import get_site_apis
    from app.design.system import ensure_design, load_design_system
    from app.experience.planner import build_plan
    from app.orchestrator.pagegen import bindable_prompt

    await ensure_design(site_key)
    await ensure_manifest(site_key)
    manifest = load_manifest(site_key)
    llm = await planner_llm(db, rt, site_key) if use_model else None
    built = await build_plan(
        db, rt, site_key, slots, intent, sig, manifest=manifest, registry=get_site_apis(site_key),
        llm=llm, model=get_settings().heavy_model, bindable=bindable_prompt(site_key),
        brand_voice=load_design_system(site_key).brand_voice, taste=taste, variant=arm, avoid=avoid)
    row = await rs.store_plan(
        db, site_key, key=key, family=intent.family, persona=sig.persona, lang=sig.lang, page=sig.page,
        regions=[s.name for s in slots], content_version=content, manifest_version=manifest.version,
        plan=built["plan"], composer=built["composer"], build_ms=built["build_ms"],
        taste=taste.bucket() if taste is not None else "", arm=arm, base_key=base_key or key)
    row["dropped"] = built["dropped"]
    row["problems"] = built["problems"]
    return row


def _schedule(token: str, coro_factory) -> None:
    """Run a build in the background, once per token at a time."""
    if token in _building:
        return
    _building.add(token)

    async def run() -> None:
        try:
            await coro_factory()
        except Exception as exc:
            logger.warning("background build failed (%s): %s", token, exc)
        finally:
            _building.discard(token)

    task = asyncio.get_running_loop().create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _schedule_build(rt: Any, site_key: str, slots: list[rs.RegionSlot], intent: Intent, sig: Signals,
                    *, key: str, content: str, taste: Any = None, arm: int = 0, base_key: Optional[str] = None,
                    avoid: str = "") -> None:
    async def build() -> None:
        from app.db import session_scope

        async with session_scope() as db:
            await build_and_store(db, rt, site_key, slots, intent, sig, key=key, content=content, taste=taste,
                                  arm=arm, base_key=base_key, avoid=avoid)

    _schedule(f"{site_key}:{key}", build)


async def pick_arm(db: AsyncSession, site_key: str, key: str, *, on_new_arm) -> Optional[dict[str, Any]]:
    """The plan for a cache key: arm 0 without the bandit, else Thompson sampling
    over the key's arms (P3-6); asks for a new arm when they've all been served enough."""
    from app.experience import bandit

    arms = await rs.plan_arms(db, site_key, key)
    if not arms:
        return await rs.cached_plan(db, site_key, key)
    settings = await rs.bandit_settings(db, site_key)
    if not settings["bandit_enabled"]:
        return arms[0]
    if bandit.wants_new_arm(arms, settings["max_arms"]):
        on_new_arm(len(arms), " > ".join(bandit.outline(arms[0]["plan"])))
    return bandit.choose_arm(arms, explore_pct=settings["explore_pct"])


async def render_plan(site_key: str, plan: dict[str, Any], ctx: dict[str, Any], *, db: Any = None,
                      rt: Any = None) -> tuple[dict[str, dict], Any]:
    """Re-validate a stored plan against today's manifest and bind live data.
    Returns ``({region name: section}, manifest)``."""
    from app.apis.registry import get_site_apis
    from app.experience.resolvers import make_resolver

    manifest = load_manifest(site_key)
    registry = get_site_apis(site_key)
    report = validate_plan(plan, manifest=manifest, catalogue=registry, site_key=site_key)
    report.plan.plan_id = plan.get("plan_id") or report.plan.plan_id
    bound = await bind_plan(report.plan, manifest=manifest, registry=registry, ctx=ctx,
                            resolve=make_resolver(db, rt, site_key) if db is not None else None)
    return {b.id: b.to_section() for b in bound if b.state == "ready"}, manifest


async def serve_regions(
    db: AsyncSession, rt: Any, site_key: str, *, names: list[str], sig: Signals,
    wait: bool = False, taste: Any = None,
) -> dict[str, Any]:
    from app.design.system import ensure_design, load_design_system
    from app.experience.personal import apply_tunables, explain
    from app.orchestrator.profile import profile_for

    out: dict[str, Any] = {"regions": {}, "pending": False}
    wanted = {n for n in names if rs.SLUG_RE.match(n)}
    slots = [s for s in await rs.list_slots(db, site_key)
             if s.enabled and s.name in wanted and s.on_page(sig.page)]
    if not slots:
        out["reason"] = "no_slots"
        return out

    intent = await intent_for(db, rt, site_key, sig)
    out["intent"] = intent.to_dict()
    await ensure_manifest(site_key)
    manifest = load_manifest(site_key)
    names_sorted = sorted(s.name for s in slots)
    content = await _content_version(db, site_key)
    bucket = taste.bucket() if taste is not None else ""
    key = rs.plan_cache_key(family=intent.family, persona=sig.persona, lang=sig.lang, page=sig.page,
                            regions=names_sorted, content_version=content, manifest_version=manifest.version,
                            taste=bucket)

    row = await rs.pinned_plan(db, site_key, family=intent.family, page=sig.page, regions=names_sorted)
    out["cache"] = "pinned" if row else "hit"
    if row is None:
        row = await pick_arm(db, site_key, key, on_new_arm=lambda n, avoid: _schedule_build(
            rt, site_key, slots, intent, sig, key=f"{key}#arm{n}", content=content, taste=taste, arm=n,
            base_key=key, avoid=avoid))
    if row is None:
        if wait:
            row = await build_and_store(db, rt, site_key, slots, intent, sig, key=key, content=content, taste=taste)
            out["cache"] = "built"
        else:
            _schedule_build(rt, site_key, slots, intent, sig, key=key, content=content, taste=taste)
            out.update(cache="miss", pending=True, retry_after_ms=RETRY_AFTER_MS)
            return out
    else:
        await rs.record_hit(db, row["id"])

    await ensure_design(site_key)
    ctx = {"site_key": site_key, "currency": profile_for(site_key).currency, "lang": sig.lang,
           "persona": sig.persona, "page": sig.page}
    regions, manifest = await render_plan(site_key, row["plan"], ctx, db=db, rt=rt)
    design = load_design_system(site_key)
    overrides, applied = apply_tunables(design, taste)
    out["regions"] = regions
    out["plan_id"] = row["plan"].get("plan_id")
    out["arm"] = row.get("arm", 0)
    out["tokens"] = {**design.to_tokens(), **overrides}
    out["why"] = explain(intent, sig, taste, served=out["cache"], applied=applied)
    if manifest.bundle and any(is_wc_renderer(s["type"]) for s in regions.values()):
        out["bundle"] = manifest.bundle
    return out


__all__ = ["serve_regions", "build_and_store", "intent_for", "render_plan", "GENERAL"]
