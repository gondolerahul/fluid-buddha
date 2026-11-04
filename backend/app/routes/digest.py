"""
Weekly digest settings and unsubscribe (M2-5).

Console (Admins):

    GET  /tenant/digest              recipients, time zone, on/off, next send
    PUT  /tenant/digest              {enabled, recipients, timezone}
    GET  /tenant/digest/preview      this week's digest as it would be sent
    POST /tenant/digest/send-test    send it now to yourself

Public (from the email):

    GET  /digest/unsubscribe?t=      a page with an Unsubscribe button
    POST /digest/unsubscribe?t=      unsubscribe (the button, and mail clients'
                                     one-click List-Unsubscribe-Post)

The GET doesn't unsubscribe by itself: link scanners open links in emails,
and that mustn't sign anyone out.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import team
from app.auth.security import current_member
from app.db import get_session, session_scope
from app.notify import digest
from app.notify import email as email_out

admin = APIRouter(prefix="/tenant/digest", tags=["digest"])
public = APIRouter(prefix="/digest", tags=["digest"])


def next_send(tz: str, now: datetime | None = None) -> str:
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(tz))
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=digest.SEND_HOUR, minute=0, second=0, microsecond=0)
    if monday <= local:
        monday += timedelta(days=7)
    return monday.isoformat()


async def _view(db: AsyncSession, m: team.Member) -> dict:
    cfg = await digest.get_settings_for(db, m.tenant.id)
    return {**cfg, "next_send": next_send(cfg["timezone"]), "you": m.email}


class DigestIn(BaseModel):
    enabled: bool
    recipients: list[EmailStr] = Field(default_factory=list, max_length=digest.MAX_RECIPIENTS)
    timezone: str = Field(digest.DEFAULT_TZ, max_length=64)


@admin.get("")
async def get_digest(m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> dict:
    return await _view(db, m)


@admin.put("")
async def put_digest(body: DigestIn, m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> dict:
    try:
        await digest.save_settings(db, m.tenant.id, enabled=body.enabled,
                                   recipients=[str(r) for r in body.recipients],
                                   tz=body.timezone, own_email=m.email)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return await _view(db, m)


@admin.get("/preview")
async def preview_digest(m: team.Member = Depends(current_member),
                         db: AsyncSession = Depends(get_session)) -> dict:
    data = await digest.build(db, m.tenant.id)
    msg = digest.render(data, account=m.tenant.name or m.tenant.email)
    return {**msg, "data": data}


@admin.post("/send-test")
async def send_test(m: team.Member = Depends(current_member),
                    db: AsyncSession = Depends(get_session)) -> dict:
    try:
        n = await digest.send_for(db, m.tenant.id, None, only=m.email)
    except email_out.EmailNotConfigured as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    await db.commit()
    return {"queued": n, "to": m.email}


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title></head>"
        '<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f5f5f2;'
        'color:#1d1f24;display:flex;justify-content:center;padding:60px 20px">'
        '<div style="background:#fff;border-radius:12px;padding:28px;max-width:420px">'
        f'<h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>{body}</div></body></html>')


@public.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(t: str = Query(..., min_length=8, max_length=100)) -> HTMLResponse:
    return _page("Stop the weekly digest?", (
        '<p style="line-height:1.5">You will no longer get the weekly FluidBuddha summary at this address.</p>'
        f'<form method="post" action="?t={escape(t)}"><button type="submit" style="background:#c9a24a;'
        'border:0;border-radius:8px;padding:10px 16px;font-weight:600;cursor:pointer">Unsubscribe</button></form>'))


@public.post("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(t: str = Query(..., min_length=8, max_length=100)) -> HTMLResponse:
    async with session_scope() as db:
        addr = await digest.unsubscribe(db, t)
    if addr is None:
        return _page("Link not recognised", "<p>This unsubscribe link isn't valid any more.</p>")
    return _page("You're unsubscribed",
                 f"<p style=\"line-height:1.5\">{escape(addr)} won't get the weekly digest again. "
                 "You can turn it back on from the console's Team page.</p>")
