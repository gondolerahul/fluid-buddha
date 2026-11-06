"""
Generative landing pages (M3-1).

Public:

    GET  /p/{site_key}/{slug}         the campaign's page, composed for this link
                                      (?persona= ?q= ?account= ?lang= utm_*), from
                                      the cache when it can be; ?embed=1 for an iframe
    POST /p/{site_key}/{slug}/lead    the page's enquiry form (a lead, a conversion)
    GET  /p/{site_key}/{slug}/go      the call to action (a conversion), then its link
    POST /p/{site_key}/{slug}/event   engagement, from the page's script

Console (reads Viewer; changes Editor):

    GET/POST        /tenant/websites/{id}/campaigns
    GET/PUT/DELETE  /tenant/websites/{id}/campaigns/{cid}
    GET             /tenant/websites/{id}/campaigns/{cid}/analytics
    POST            /tenant/websites/{id}/campaigns/{cid}/cache/clear
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import team
from app.auth.security import current_member
from app.campaigns import compose as composer
from app.campaigns import page
from app.campaigns import store as campaigns
from app.config import get_settings
from app.db import get_session, session_scope
from app.design.system import ensure_design, load_design_system
from app.experiments.bots import is_bot
from app.orchestrator.profile import ensure_profile
from app.tenancy import store as tenancy
from app.tenancy.deps import owned_website
from app.transport import guard

logger = logging.getLogger(__name__)

public = APIRouter(tags=["campaigns"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["campaigns"])

VIEWER_COOKIE = "fb_pv"
COMPOSE_PER_MIN = 20      # fresh compositions per site per minute (cached pages are free)
LEAD_PER_MIN = 10         # enquiries per client address per minute
ENGAGE_GAP_S = 1800


def page_path(site_key: str, slug: str) -> str:
    return f"/p/{site_key}/{slug}"


def page_url(site_key: str, slug: str) -> str:
    return get_settings().public_api_url.rstrip("/") + page_path(site_key, slug)


def preview_token(campaign_id: Any, version: int) -> str:
    """Opens a draft (or an edited live campaign) for its editors; changes with every edit."""
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"campaign-preview:{campaign_id}:{version}".encode(), hashlib.sha256).hexdigest()[:32]


def _viewer(request: Request) -> tuple[str, bool]:
    v = request.cookies.get(VIEWER_COOKIE) or ""
    if 16 <= len(v) <= 64:
        return v, False
    return secrets.token_urlsafe(16), True


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


async def _load(db: AsyncSession, site_key: str, slug: str
                ) -> tuple[Optional[tenancy.Website], Optional[campaigns.Campaign]]:
    site = await tenancy.get_website_by_site_key(db, site_key)
    if site is None or site.status != "active":
        return None, None
    return site, await campaigns.by_slug(db, site_key, slug)


def _html(body: str, *, status_code: int = 200, csp: Optional[str] = None,
          extra: Optional[dict[str, str]] = None) -> HTMLResponse:
    headers = {"Content-Security-Policy": csp or "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
               "X-Robots-Tag": "noindex", "Cache-Control": "private, no-store",
               "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin",
               **(extra or {})}
    return HTMLResponse(body, status_code=status_code, headers=headers)


async def _llm_for(rt: Any, site_key: str) -> Any:
    """The account's own model (M3-4) or the platform's; none in mock mode."""
    from app.ai.providers import config_for_site, current_site

    current_site.set(site_key)
    settings = get_settings()
    byo = await config_for_site(site_key)
    return rt.engines.llm if (byo is not None or not settings.mock_ai) else None


async def _record_usage(site_key: str, spec: dict[str, Any]) -> None:
    tin, tout = (spec.get("tokens") or [0, 0])[:2]
    if not (tin or tout):
        return
    from app.analytics.usage import TurnMetrics, record_turn
    try:
        async with session_scope() as adb:
            m = TurnMetrics(site_key=site_key, session_id=None, channel="campaign", intent="landing_page",
                            persona=spec.get("persona"), latency_ms=float(spec.get("build_ms") or 0))
            m.add_llm(kind="thinker", input_tokens=tin, output_tokens=tout)
            await record_turn(adb, m)
    except Exception as exc:
        logger.debug("campaign usage record skipped: %s", exc)


async def page_for(db: AsyncSession, rt: Any, c: campaigns.Campaign, ctx: composer.Context, *,
                   bot: bool = False) -> tuple[dict[str, Any], bool, float]:
    """The page for this context: from the cache, else composed (and cached).
    Returns ``(spec, from_cache, ms)``."""
    t0 = time.monotonic()
    content = await campaigns.content_version(db, c.site_key)
    key = campaigns.cache_key(c, arm=ctx.arm, persona=ctx.persona, question=ctx.question, lang=ctx.lang,
                              content=content)
    spec = await campaigns.cached_page(db, c.id, key)
    if spec is not None:
        await db.commit()
        return spec, True, (time.monotonic() - t0) * 1000
    # Link previews and crawlers get a page already composed, if there is one.
    if bot:
        spec = await campaigns.any_cached_page(db, c.id, ctx.arm)
        if spec is not None:
            return spec, True, (time.monotonic() - t0) * 1000
    llm = None
    if guard._limiter.allow(f"campaign-compose:{c.site_key}", COMPOSE_PER_MIN):
        blocked = await guard.check_public_budget(db, c.site_key, get_settings())
        if not blocked:
            llm = await _llm_for(rt, c.site_key)
    else:
        spec = await campaigns.any_cached_page(db, c.id, ctx.arm)
        if spec is not None:
            return spec, True, (time.monotonic() - t0) * 1000
    # Past the rate or the spend cap, the rules compose it: they cost nothing.
    await ensure_profile(c.site_key)
    spec = await composer.compose(db, rt, c, ctx, llm=llm, model=get_settings().heavy_model)
    await campaigns.store_page(db, c.id, key, arm=ctx.arm, persona=ctx.persona, question=ctx.question,
                               spec=spec, composer=spec["composer"], build_ms=spec["build_ms"])
    await db.commit()
    await _record_usage(c.site_key, spec)
    return spec, False, (time.monotonic() - t0) * 1000


def _frame_ancestors(site: tenancy.Website, c: campaigns.Campaign) -> list[str]:
    out = list(c.embed_origins)
    if site.domain:
        d = site.domain.strip().lower()
        out += [f"https://{d}", f"https://*.{d}"]
    return list(dict.fromkeys(out))


@public.get("/p/{site_key}/{slug}", response_class=HTMLResponse)
async def view(site_key: str, slug: str, request: Request) -> HTMLResponse:
    settings = get_settings()
    rt = request.app.state.runtime
    params = dict(request.query_params)
    viewer, fresh = _viewer(request)
    bot = is_bot(request.headers.get("user-agent"))
    async with session_scope() as db:
        site, c = await _load(db, site_key, slug)
        if site is None or c is None:
            return _html(page.message("This page isn't available", "The link may be wrong or the page was removed."), status_code=404)
        preview = bool(params.get("preview")) and hmac.compare_digest(str(params.get("preview")), preview_token(c.id, c.version))
        if c.status != "live" and not preview:
            return _html(page.message("This page isn't available yet", "Check back soon."), status_code=404)
        profile = await ensure_profile(site_key)
        arm = params.get("arm") if preview and params.get("arm") in ("a", "b") else campaigns.assign_arm(c, viewer)
        ctx = composer.context_from(params, c, personas=profile.persona_slugs, languages=profile.languages, arm=arm)
        spec, cached, ms = await page_for(db, rt, c, ctx, bot=bot)
        if not (bot or preview):
            await campaigns.record(db, c, viewer=viewer, kind="view", arm=arm, persona=ctx.persona,
                                   source=ctx.source, cached=cached)
            await db.commit()
    await ensure_design(site_key)
    design = load_design_system(site_key)
    site_url = f"https://{site.domain}" if site.domain else None
    embed = params.get("embed") == "1"
    html = page.render(
        spec, company=profile.company_name, design=design, public_key=site.public_key or "",
        api_base=settings.public_api_url, sdk_base=settings.widget_sdk_base, base_path=page_path(site_key, slug),
        query={**params, "account_clean": ctx.account or ""}, site_url=site_url, cta_url=c.cta_url,
        embed=embed, sent=params.get("sent") == "1", preview=preview)
    csp = page.csp(api_base=settings.public_api_url, sdk_base=settings.widget_sdk_base,
                   frame_ancestors=_frame_ancestors(site, c) if embed else [])
    resp = _html(html, csp=csp, extra={
        "Server-Timing": f'compose;desc="{"cache" if cached else spec.get("composer", "rules")}";dur={ms:.1f}'})
    if fresh:
        resp.set_cookie(VIEWER_COOKIE, viewer, max_age=2 * 365 * 86400, httponly=True, path="/p",
                        samesite="none" if embed and request.url.scheme == "https" else "lax",
                        secure=request.url.scheme == "https")
    return resp


def _back(site_key: str, slug: str, form: dict[str, str], extra: dict[str, str]) -> str:
    keep = {k: v for k, v in form.items() if k in ("persona", "q", "account", "lang") or k.startswith("utm_")}
    return page_path(site_key, slug) + "?" + urlencode({**keep, **extra}) + "#enquiry"


@public.post("/p/{site_key}/{slug}/lead")
async def lead(site_key: str, slug: str, request: Request, background: BackgroundTasks) -> Response:
    from app.leads import delivery
    from app.leads import store as leads

    form = {k: str(v)[:2000] for k, v in (await request.form()).items()}
    viewer, _ = _viewer(request)
    if form.get("website"):            # the hidden field only bots fill in
        return RedirectResponse(_back(site_key, slug, form, {"sent": "1"}), status_code=303)
    if not guard._limiter.allow(f"campaign-lead:{_client_ip(request)}", LEAD_PER_MIN):
        return _html(page.message("Too many tries", "Please wait a minute and try again."), status_code=429)
    async with session_scope() as db:
        site, c = await _load(db, site_key, slug)
        if site is None or c is None or c.status != "live":
            return _html(page.message("This page isn't available", "The link may be wrong."), status_code=404)
        profile = await ensure_profile(site_key)
        persona = form.get("persona") if form.get("persona") in profile.persona_slugs else c.persona
        try:
            row = await leads.create_lead(db, site_key=site_key, source="campaign", persona=persona, lead=leads.LeadIn(
                email=form.get("email") or "", name=form.get("name") or None, company=form.get("company") or None,
                message=form.get("message") or None, interest=f"Campaign: {c.name}"))
        except leads.LeadError as exc:
            return _html(page.message("Please check the form", str(exc).capitalize() + "."), status_code=422)
        await campaigns.record(db, c, viewer=viewer, kind="convert", arm=campaigns.assign_arm(c, viewer),
                               persona=persona, source=(form.get("utm_source") or "")[:60].lower() or None)
        await db.commit()
    background.add_task(delivery.deliver_lead, row)
    return RedirectResponse(_back(site_key, slug, form, {"sent": "1"}), status_code=303)


@public.get("/p/{site_key}/{slug}/go")
async def go(site_key: str, slug: str, request: Request) -> Response:
    viewer, _ = _viewer(request)
    async with session_scope() as db:
        site, c = await _load(db, site_key, slug)
        if site is None or c is None or c.status != "live" or not c.cta_url:
            return RedirectResponse(page_path(site_key, slug), status_code=302)
        if not is_bot(request.headers.get("user-agent")):
            persona = request.query_params.get("persona")
            await campaigns.record(db, c, viewer=viewer, kind="convert", arm=campaigns.assign_arm(c, viewer),
                                   persona=persona if persona else c.persona,
                                   source=(request.query_params.get("utm_source") or "")[:60].lower() or None)
            await db.commit()
    return RedirectResponse(c.cta_url, status_code=302)


@public.post("/p/{site_key}/{slug}/event", status_code=status.HTTP_204_NO_CONTENT)
async def event(site_key: str, slug: str, request: Request) -> Response:
    try:
        body = json.loads((await request.body())[:2000] or b"{}")
    except ValueError:
        body = {}
    viewer = request.cookies.get(VIEWER_COOKIE) or ""
    if body.get("kind") != "engage" or not (16 <= len(viewer) <= 64) or is_bot(request.headers.get("user-agent")):
        return Response(status_code=204)
    if not guard._limiter.allow(f"campaign-event:{viewer}", 6):
        return Response(status_code=204)
    async with session_scope() as db:
        site, c = await _load(db, site_key, slug)
        if site is None or c is None or c.status != "live":
            return Response(status_code=204)
        from sqlalchemy import text
        recent = (await db.execute(text(
            "SELECT 1 FROM campaign_events WHERE campaign_id = :c AND viewer = :v AND kind = 'engage' "
            "AND created_at > now() - make_interval(secs => :g) LIMIT 1"),
            {"c": c.id, "v": viewer, "g": ENGAGE_GAP_S})).first()
        if not recent:
            persona = str(body.get("persona") or "")[:40] or c.persona
            await campaigns.record(db, c, viewer=viewer, kind="engage", arm=campaigns.assign_arm(c, viewer),
                                   persona=persona)
            await db.commit()
    return Response(status_code=204)


# ---- console ---------------------------------------------------------------------------

def _out(site: tenancy.Website, c: campaigns.Campaign | dict) -> dict[str, Any]:
    d = c.public() if isinstance(c, campaigns.Campaign) else dict(c)
    d["url"] = page_url(site.site_key, d["slug"])
    d["preview_url"] = d["url"] + "?preview=" + preview_token(d["id"], d["version"])
    domain = site.domain or "your-site.com"
    d["embed_snippet"] = (f'<iframe src="{d["url"]}?embed=1" title="{d["name"]}" loading="lazy" '
                          'style="width:100%;min-height:900px;border:0"></iframe>')
    d["embed_note"] = f"Pages may be framed by https://{domain} and the origins you list."
    return d


async def _personas(site_key: str) -> list[dict[str, str]]:
    profile = await ensure_profile(site_key)
    return [{"slug": p.slug, "label": p.label} for p in profile.personas]


@admin.get("/campaigns")
async def list_campaigns(site: tenancy.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> dict:
    items = await campaigns.list_for_site(db, site.site_key)
    return {"campaigns": [_out(site, c) for c in items], "personas": await _personas(site.site_key),
            "sections": [{"type": t, "label": campaigns.SECTION_LABELS[t]} for t in campaigns.LANDING_SECTIONS],
            "default_sections": list(campaigns.DEFAULT_SECTIONS)}


@admin.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(body: dict, site: tenancy.Website = Depends(owned_website),
                          m: team.Member = Depends(current_member),
                          db: AsyncSession = Depends(get_session)) -> dict:
    personas = [p["slug"] for p in await _personas(site.site_key)]
    try:
        c = await campaigns.create(db, site.site_key, campaigns.clean(body, personas=personas), m.user_id)
    except campaigns.CampaignError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await db.commit()
    return _out(site, c)


async def _get(db: AsyncSession, site: tenancy.Website, cid: uuid.UUID) -> campaigns.Campaign:
    c = await campaigns.get(db, site.site_key, cid)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign")
    return c


@admin.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: uuid.UUID, site: tenancy.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    return _out(site, await _get(db, site, campaign_id))


@admin.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: uuid.UUID, body: dict, site: tenancy.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> dict:
    c = await _get(db, site, campaign_id)
    personas = [p["slug"] for p in await _personas(site.site_key)]
    try:
        c = await campaigns.update(db, c, campaigns.clean(body, personas=personas))
    except campaigns.CampaignError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await db.commit()
    return _out(site, c)


@admin.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: uuid.UUID, site: tenancy.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> None:
    if not await campaigns.delete(db, site.site_key, campaign_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such campaign")
    await db.commit()


@admin.get("/campaigns/{campaign_id}/analytics")
async def campaign_analytics(campaign_id: uuid.UUID, days: int = 30,
                             site: tenancy.Website = Depends(owned_website),
                             db: AsyncSession = Depends(get_session)) -> dict:
    c = await _get(db, site, campaign_id)
    return await campaigns.analytics(db, c, days=max(1, min(days, 365)))


@admin.post("/campaigns/{campaign_id}/cache/clear")
async def clear_campaign_cache(campaign_id: uuid.UUID, site: tenancy.Website = Depends(owned_website),
                               db: AsyncSession = Depends(get_session)) -> dict:
    c = await _get(db, site, campaign_id)
    n = await campaigns.clear_cache(db, c.id)
    await db.commit()
    return {"cleared": n}
