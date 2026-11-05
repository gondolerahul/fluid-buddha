"""
Shareable recap pages (M2-6).

Public:

    POST /recap      {key, site?, session_id, email?} → {url, expires_at, emailed}
                     Build (or refresh) the session's recap. With ``email``
                     the link is emailed too, and the address becomes a lead.
    GET  /r/{token}  the recap page (views and forwards counted)

Console:

    GET    /tenant/websites/{id}/recaps          recent recaps with views and forwards
    DELETE /tenant/websites/{id}/recaps/{rid}    take a link down
"""
from __future__ import annotations

import logging
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session, session_scope
from app.design.system import ensure_design, load_design_system
from app.experiments.bots import is_bot
from app.leads import delivery
from app.leads import store as leads
from app.notify import email as email_out
from app.notify import templates
from app.orchestrator.profile import ensure_profile
from app.recaps import page
from app.recaps import store as recaps
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.transport import guard
from app.trust.settings import get_privacy

logger = logging.getLogger(__name__)

public = APIRouter(tags=["recaps"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["recaps"])

RECAP_RATE_PER_MIN = 30
VIEWER_COOKIE = "fb_rv"


def recap_url(token: str) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/r/{token}"


class RecapRequest(BaseModel):
    key: Optional[str] = None
    site: Optional[str] = None
    session_id: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=320)


@public.post("/recap")
async def make_recap(body: RecapRequest, request: Request, background: BackgroundTasks) -> dict:
    settings = get_settings()
    rt = request.app.state.runtime
    async with session_scope() as db:
        try:
            resolved = await resolve_public_site(db, key=body.key, site=body.site, intelligence=None,
                                                 origin=request.headers.get("origin"))
        except PublicAccessError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
        if not guard._limiter.allow(f"recap:{resolved.site_key}", RECAP_RATE_PER_MIN):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
        blocked = await guard.check_public_budget(db, resolved.site_key, settings,
                                                  session_id=body.session_id)
        if blocked:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
        privacy = await get_privacy(db, resolved.site_key)
        llm = None if settings.mock_ai else rt.engines.llm
        try:
            recap = await recaps.create_or_refresh(
                db, resolved.site_key, body.session_id, recap_days=privacy.recap_days,
                llm=llm, model=settings.fast_model)
        except recaps.NothingToRecap:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nothing to recap yet: ask a question first.")
        url = recap_url(recap["token"])

        emailed = False
        if body.email:
            try:
                lead = await leads.create_lead(
                    db, site_key=resolved.site_key, session_id=body.session_id, source="recap",
                    lead=leads.LeadIn(email=body.email, interest="Asked for a recap of the conversation"))
            except leads.LeadError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
            profile = await ensure_profile(resolved.site_key)
            company = profile.company_name
            try:
                await email_out.enqueue(db, email_out.Email(
                    to=lead["email"], subject=f"Your conversation with {company}",
                    text=f"Here's a recap of your conversation with {company}:\n{url}\n\n"
                         "Feel free to forward it to your team.",
                    html=templates.layout(
                        f"Your conversation with {company}",
                        templates.paragraph("Here's a recap of what you asked and the answers, with "
                                            "anything that was shown. Feel free to forward it to your team.")
                        + templates.button("Open the recap", url)),
                    kind="recap", idem_key=f"recap:{recap['id']}:{lead['email']}"))
                emailed = True
            except email_out.EmailNotConfigured:
                logger.warning("recap email skipped: email isn't configured")
            await db.commit()
            background.add_task(delivery.deliver_lead, lead)
    return {"url": url, "expires_at": recap["expires_at"].isoformat(), "emailed": emailed}


def _html(body: str, status_code: int = 200, csp: str = "default-src 'none'; style-src 'unsafe-inline'") -> HTMLResponse:
    return HTMLResponse(body, status_code=status_code, headers={
        "Content-Security-Policy": csp, "Referrer-Policy": "no-referrer",
        "X-Robots-Tag": "noindex, nofollow", "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@public.get("/r/{token}", response_class=HTMLResponse)
async def view_recap(token: str, request: Request) -> HTMLResponse:
    settings = get_settings()
    viewer = request.cookies.get(VIEWER_COOKIE) or ""
    fresh = not (16 <= len(viewer) <= 64)
    if fresh:
        viewer = secrets.token_urlsafe(16)
    async with session_scope() as db:
        recap = await recaps.by_token(db, token)
        if recap is None:
            return _html(page.not_found(), 404)
        site = (await db.execute(text(
            "SELECT name, domain FROM tenant_websites WHERE site_key = :s"),
            {"s": recap["site_key"]})).mappings().first()
        # Link previews (Slack, mail scanners) aren't people: not counted.
        if not is_bot(request.headers.get("user-agent")):
            await recaps.record_view(db, recap, viewer)
    profile = await ensure_profile(recap["site_key"])
    await ensure_design(recap["site_key"])
    design = load_design_system(recap["site_key"])
    domain = (site and site["domain"]) or ""
    first = recap["content"].get("first_page") or "/"
    site_url = f"https://{domain}{first if first.startswith('/') else '/'}" if domain else None
    html = page.render(recap, company=profile.company_name, agent_name=profile.agent_name,
                       design=design, site_url=site_url, cta_label=profile.cta_label,
                       cta_url=profile.cta_url, sdk_base=settings.widget_sdk_base)
    resp = _html(html, csp=page.csp(settings.widget_sdk_base, frames=page.embed_origins(recap)))
    if fresh:
        resp.set_cookie(VIEWER_COOKIE, viewer, max_age=2 * 365 * 86400, httponly=True,
                        samesite="lax", path="/r", secure=request.url.scheme == "https")
    return resp


@admin.get("/recaps")
async def list_recaps(site: store.Website = Depends(owned_website),
                      db: AsyncSession = Depends(get_session)) -> dict:
    items = await recaps.list_for_site(db, site.site_key)
    for it in items:
        it["url"] = recap_url(it.pop("token"))
    return {"recaps": items}


@admin.delete("/recaps/{recap_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_recap(recap_id: uuid.UUID, site: store.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> None:
    if not await recaps.revoke(db, site.site_key, recap_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such recap")
