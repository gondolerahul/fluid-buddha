"""
Console sessions (M2-11).

Every sign-in (password, password + two-factor, SSO, accepting an invitation,
switching account) creates a row in ``user_sessions``. The token names it
(``sid``), so a session:

* ends after ``SESSION_IDLE_MINUTES`` without a request, and after
  ``SESSION_ABSOLUTE_HOURS`` whatever happens;
* can be revoked: sign out, sign out everywhere, a password change, losing
  membership of the account.

The console holds the token in an **httpOnly cookie** (``fb_session``), so page
scripts can't read it. Cookie-authenticated changes must carry
``X-CSRF-Token`` — an HMAC of the session id the server hands back at sign-in
and from ``/auth/me``. Bearer tokens (API clients, tests) work as before and
need no CSRF token, since a browser never sends them by itself.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings

COOKIE = "fb_session"
TOUCH_EVERY = timedelta(seconds=60)


@dataclass
class Session:
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    method: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime

    @property
    def mfa(self) -> bool:
        """Signed in with a second factor (or through the organisation's IdP)."""
        return self.method.endswith("+totp") or self.method.startswith("sso")


def csrf_for(session_id: uuid.UUID | str, settings: Optional[Settings] = None) -> str:
    key = (settings or get_settings()).jwt_secret.encode()
    mac = hmac.new(key, f"csrf:{session_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def check_csrf(session_id: uuid.UUID, header: Optional[str]) -> bool:
    return bool(header) and hmac.compare_digest(csrf_for(session_id), header or "")


def _client(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    return ip, (request.headers.get("user-agent") or "")[:300] or None


async def start(db: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID, method: str,
                request: Optional[Request] = None) -> Session:
    s = get_settings()
    now = datetime.now(timezone.utc)
    sid = uuid.uuid4()
    ip, ua = _client(request)
    expires = now + timedelta(hours=s.session_absolute_hours)
    await db.execute(text(
        "INSERT INTO user_sessions (id, user_id, tenant_id, method, created_at, last_seen_at, "
        "expires_at, ip, user_agent) VALUES (:id, :u, :t, :m, :now, :now, :exp, :ip, :ua)"),
        {"id": sid, "u": user_id, "t": tenant_id, "m": method, "now": now, "exp": expires,
         "ip": ip, "ua": ua})
    return Session(id=sid, user_id=user_id, tenant_id=tenant_id, method=method,
                   created_at=now, last_seen_at=now, expires_at=expires)


async def active(db: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Session]:
    """The session if it is still live (and marks it used); else None."""
    row = (await db.execute(text(
        "SELECT id, user_id, tenant_id, method, created_at, last_seen_at, expires_at, revoked_at "
        "FROM user_sessions WHERE id = :id AND user_id = :u"),
        {"id": session_id, "u": user_id})).mappings().first()
    if not row or row["revoked_at"] is not None:
        return None
    now = datetime.now(timezone.utc)
    idle = timedelta(minutes=get_settings().session_idle_minutes)
    if now >= row["expires_at"] or now - row["last_seen_at"] > idle:
        return None
    if now - row["last_seen_at"] > TOUCH_EVERY:
        await db.execute(text("UPDATE user_sessions SET last_seen_at = :now WHERE id = :id"),
                         {"now": now, "id": session_id})
        await db.commit()
    return Session(**{k: row[k] for k in ("id", "user_id", "tenant_id", "method", "created_at",
                                          "last_seen_at", "expires_at")})


async def set_method(db: AsyncSession, session_id: uuid.UUID, method: str) -> None:
    await db.execute(text("UPDATE user_sessions SET method = :m WHERE id = :id"),
                     {"m": method, "id": session_id})


async def revoke(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(text(
        "UPDATE user_sessions SET revoked_at = now() WHERE id = :id AND revoked_at IS NULL"),
        {"id": session_id})


async def revoke_all(db: AsyncSession, user_id: uuid.UUID, *, tenant_id: Optional[uuid.UUID] = None,
                     keep: Optional[uuid.UUID] = None) -> int:
    """End a person's sessions (in one account, or everywhere), except ``keep``."""
    res = await db.execute(text(
        "UPDATE user_sessions SET revoked_at = now() WHERE user_id = :u AND revoked_at IS NULL "
        "AND (CAST(:t AS uuid) IS NULL OR tenant_id = :t) "
        "AND (CAST(:k AS uuid) IS NULL OR id <> :k)"),
        {"u": user_id, "t": tenant_id, "k": keep})
    return res.rowcount or 0


async def list_for(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    idle = get_settings().session_idle_minutes
    rows = (await db.execute(text(
        "SELECT s.id, s.method, s.created_at, s.last_seen_at, s.ip, s.user_agent, "
        "COALESCE(t.name, t.email) AS account FROM user_sessions s JOIN tenants t ON t.id = s.tenant_id "
        "WHERE s.user_id = :u AND s.revoked_at IS NULL AND s.expires_at > now() "
        "AND s.last_seen_at > now() - make_interval(mins => :idle) "
        "ORDER BY s.last_seen_at DESC LIMIT 50"), {"u": user_id, "idle": idle})).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat(),
             "last_seen_at": r["last_seen_at"].isoformat()} for r in rows]


# ---- the cookie -----------------------------------------------------------------------

def set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE, token,
        max_age=s.session_absolute_hours * 3600,
        httponly=True,
        secure=s.session_cookie_secure if s.session_cookie_secure is not None else not s.is_dev_env,
        samesite=s.session_cookie_samesite,
        domain=s.session_cookie_domain or None,
        path="/",
    )


def clear_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(COOKIE, path="/", domain=s.session_cookie_domain or None)
