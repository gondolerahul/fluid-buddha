"""
Single sign-on routes (M2-1). The flow and the rules are in ``app.auth.sso``.

Signing in:
    POST /auth/sso/start      {provider: "google" | "oidc", email?} → {url}
    GET  /auth/sso/callback   (the identity provider redirects here) → back to
                              the console with the token in the URL fragment

The account's own identity provider (Owner changes, Admins can look):
    GET    /tenant/sso                  settings, domains and the redirect URI
    PUT    /tenant/sso                  {issuer, client_id, client_secret?,
                                         default_role, require_sso, enabled}
    DELETE /tenant/sso
    POST   /tenant/sso/domains          {domain} → the TXT record to publish
    POST   /tenant/sso/domains/{domain}/verify
    DELETE /tenant/sso/domains/{domain}
"""
from __future__ import annotations

import logging
import secrets
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import sessions, sso, team
from app.auth.security import create_access_token, current_member
from app.config import get_settings
from app.db import get_session
from app.security import secrets as stored

logger = logging.getLogger(__name__)
public = APIRouter(prefix="/auth/sso", tags=["sso"])
admin = APIRouter(prefix="/tenant/sso", tags=["sso"])


class StartIn(BaseModel):
    provider: Literal["google", "oidc"] = "oidc"
    email: Optional[str] = Field(None, max_length=320)


@public.post("/start")
async def start(body: StartIn, db: AsyncSession = Depends(get_session)) -> dict:
    try:
        url = await sso.start(db, provider=body.provider, email=body.email)
    except sso.SSOError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    await db.commit()
    return {"url": url}


def _to_console(path: str) -> str:
    return get_settings().console_url.rstrip("/") + path


async def _sign_in(db: AsyncSession, ident: sso.Identity) -> team.Member:
    p = ident.provider
    user = await team.user_by_email(db, ident.email)
    if p.tenant_id is None:   # Google: only people who already belong somewhere
        m = await team.member(db, user["id"], None) if user else None
        if m is None:
            raise sso.SSOError(f"There's no FluidBuddha account for {ident.email}. "
                               "Ask your admin for an invitation, or sign up first.")
        return m
    user_id = user["id"] if user else await team.create_user(
        db, email=ident.email, name=ident.name, password_hash=None)
    if await team.role_of(db, p.tenant_id, user_id) is None:
        await team.add_member(db, user_id, p.tenant_id, p.default_role)
    m = await team.member(db, user_id, p.tenant_id)
    assert m is not None
    return m


@public.get("/callback")
async def callback(request: Request, state: str = "", code: str = "", error: str = "",
                   error_description: str = "",
                   db: AsyncSession = Depends(get_session)) -> RedirectResponse:
    try:
        if error:
            raise sso.SSOError(error_description or f"The identity provider said: {error}")
        if not code or not state:
            raise sso.SSOError("The sign-in response was incomplete. Please try again.")
        ident = await sso.finish(db, state=state, code=code)
        m = await _sign_in(db, ident)
    except sso.SSOError as exc:
        return RedirectResponse(_to_console(f"/login?sso_error={quote(str(exc))}"), 303)
    await team.touch_login(db, m.user_id)
    await audit.record(db, action="login", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, details={"method": f"sso:{ident.provider.name}"},
                       **audit.request_meta(request))
    await db.commit()
    # The session cookie rides on the redirect (M2-11); the console's /sso page
    # then reads who signed in from /auth/me. No token in the address.
    sess = await sessions.start(db, user_id=m.user_id, tenant_id=m.tenant.id,
                                method=f"sso:{ident.provider.name}", request=request)
    await db.commit()
    token = create_access_token(m.user_id, m.tenant.id, session_id=sess.id,
                                expires_at=sess.expires_at)
    out = RedirectResponse(_to_console("/sso"), 303)
    sessions.set_cookie(out, token)
    return out


# ---- the account's identity provider ---------------------------------------------------

class SSOConfigIn(BaseModel):
    issuer: str = Field(..., max_length=500)
    client_id: str = Field(..., min_length=1, max_length=500)
    client_secret: Optional[str] = Field(None, max_length=2000)   # omit to keep
    default_role: Literal["admin", "editor", "viewer"] = "viewer"
    require_sso: bool = False
    enabled: bool = True


async def _config(db: AsyncSession, tenant_id) -> dict:
    row = (await db.execute(text(
        "SELECT issuer, client_id, client_secret_enc IS NOT NULL AS has_secret, default_role, "
        "require_sso, enabled, updated_at FROM tenant_sso WHERE tenant_id = :t"),
        {"t": tenant_id})).mappings().first()
    domains = (await db.execute(text(
        "SELECT domain, token, verified_at FROM sso_domains WHERE tenant_id = :t ORDER BY domain"),
        {"t": tenant_id})).mappings().all()
    return {
        "configured": row is not None,
        **({k: v for k, v in dict(row).items() if k != "updated_at"} if row else {}),
        "redirect_uri": sso.redirect_uri(),
        "domains": [{"domain": d["domain"], "verified": d["verified_at"] is not None,
                     "txt_name": d["domain"], "txt_value": sso.txt_value(d["token"])}
                    for d in domains],
    }


@admin.get("")
async def get_sso(m: team.Member = Depends(current_member),
                  db: AsyncSession = Depends(get_session)) -> dict:
    return await _config(db, m.tenant.id)


@admin.put("")
async def put_sso(body: SSOConfigIn, m: team.Member = Depends(current_member),
                  db: AsyncSession = Depends(get_session)) -> dict:
    issuer = body.issuer.strip().rstrip("/")
    try:
        await sso.discover(issuer)   # a wrong issuer fails now, not at sign-in
    except sso.SSOError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    enc = stored.encrypt(body.client_secret) if body.client_secret else None
    await db.execute(text(
        "INSERT INTO tenant_sso (tenant_id, issuer, client_id, client_secret_enc, default_role, "
        "require_sso, enabled) VALUES (:t, :i, :c, :s, :r, :q, :e) "
        "ON CONFLICT (tenant_id) DO UPDATE SET issuer = EXCLUDED.issuer, "
        "client_id = EXCLUDED.client_id, client_secret_enc = COALESCE(EXCLUDED.client_secret_enc, "
        "tenant_sso.client_secret_enc), default_role = EXCLUDED.default_role, "
        "require_sso = EXCLUDED.require_sso, enabled = EXCLUDED.enabled, updated_at = now()"),
        {"t": m.tenant.id, "i": issuer, "c": body.client_id.strip(), "s": enc,
         "r": body.default_role, "q": body.require_sso, "e": body.enabled})
    await db.commit()
    return await _config(db, m.tenant.id)


@admin.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sso(m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> None:
    await db.execute(text("DELETE FROM tenant_sso WHERE tenant_id = :t"), {"t": m.tenant.id})
    await db.commit()


class DomainIn(BaseModel):
    domain: str = Field(..., max_length=253)


@admin.post("/domains", status_code=status.HTTP_201_CREATED)
async def add_domain(body: DomainIn, m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> dict:
    domain = body.domain.strip().lower().removeprefix("@")
    if not sso.DOMAIN_RE.match(domain):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That isn't a domain name.")
    # A domain belongs to one account. An unproven claim older than a week can
    # be taken over, so nobody can squat on a domain they don't own.
    taken = (await db.execute(text(
        "SELECT tenant_id, verified_at IS NOT NULL OR created_at > now() - interval '7 days' "
        "AS held FROM sso_domains WHERE domain = :d"), {"d": domain})).first()
    if taken and taken[0] != m.tenant.id and taken[1]:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Another account has claimed this domain.")
    if not taken or taken[0] != m.tenant.id:
        await db.execute(text(
            "INSERT INTO sso_domains (domain, tenant_id, token) VALUES (:d, :t, :k) "
            "ON CONFLICT (domain) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, "
            "token = EXCLUDED.token, created_at = now(), verified_at = NULL"),
            {"d": domain, "t": m.tenant.id, "k": secrets.token_urlsafe(24)})
        await db.commit()
    return next(d for d in (await _config(db, m.tenant.id))["domains"] if d["domain"] == domain)


@admin.post("/domains/{domain}/verify")
async def verify_domain(domain: str, m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> dict:
    domain = domain.strip().lower()
    try:
        ok = await sso.verify_domain(db, m.tenant.id, domain)
    except sso.SSOError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"DNS lookup failed: {exc}")
    await db.commit()
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The TXT record isn't visible yet. DNS changes can take up to an "
                            "hour; try again later.")
    return {"domain": domain, "verified": True}


@admin.delete("/domains/{domain}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(domain: str, m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> None:
    await db.execute(text("DELETE FROM sso_domains WHERE domain = :d AND tenant_id = :t"),
                     {"d": domain.strip().lower(), "t": m.tenant.id})
    await db.commit()
