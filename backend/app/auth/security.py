"""
Password hashing (bcrypt) + JWT bearer tokens + the ``current_member`` FastAPI
dependency that guards every tenant-scoped route (req A, M2-1).

A token names a person (``sub`` = user id) and the account they act in
(``tid``). The role is read from the database on every request, so a role
change or removal takes effect at once, and the request is checked against
``app.auth.roles`` before the route runs. ``current_tenant`` (the account) is
kept for routes that only need that.

bcrypt is used directly (no passlib) to avoid passlib's brittle bcrypt-version
probing on bcrypt 4.x. bcrypt hashes at most 72 bytes of input, so we hash the
SHA-256 of the password first — this removes the truncation foot-gun and lets
arbitrarily long passwords work.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.auth import roles, sessions, team
from app.tenancy import store

_bearer = HTTPBearer(auto_error=False)


# ---- password hashing -----------------------------------------------------
def _prehash(password: str) -> bytes:
    """SHA-256 the password to a fixed 32-byte digest (hex) so bcrypt's 72-byte
    limit never truncates a real password."""
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ---- JWT ------------------------------------------------------------------
def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID | None = None,
                        settings: Settings | None = None, *,
                        session_id: uuid.UUID | None = None,
                        expires_at: datetime | None = None) -> str:
    """A token for a session (``sid``). Since M2-11 only tokens that name a
    live session are accepted; see ``app.auth.sessions``."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    exp = expires_at or now + timedelta(hours=settings.session_absolute_hours)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    if session_id is not None:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---- dependencies -----------------------------------------------------------
_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)
_EXPIRED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Your session has ended. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)

# Reachable while an account that requires two-factor waits for this person to
# set it up (everything else answers 403 mfa_setup_required).
_MFA_SETUP_PATHS = ("/auth/me", "/auth/mfa", "/auth/logout", "/auth/sessions", "/auth/accounts",
                    "/auth/switch", "/auth/password")


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


def request_token(request: Request, creds: HTTPAuthorizationCredentials | None) -> tuple[str, bool]:
    """The bearer token, else the session cookie; and whether it was the cookie."""
    if creds is not None and creds.credentials:
        return creds.credentials, False
    cookie = request.cookies.get(sessions.COOKIE)
    return (cookie, True) if cookie else ("", False)


async def member_from_token(db: AsyncSession, token: str) -> tuple[team.Member, sessions.Session]:
    """The member and live session a token belongs to, or 401."""
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
        sid = uuid.UUID(payload["sid"]) if payload.get("sid") else None
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTH
    if sid is None:
        raise _EXPIRED   # tokens from before sessions (M2-11): sign in once more
    sess = await sessions.active(db, sid, user_id)
    if sess is None:
        raise _EXPIRED
    m = await team.member(db, user_id, sess.tenant_id)
    if m is None:
        raise _UNAUTH
    m.session_id = sess.id
    m.session_mfa = sess.mfa
    return m, sess


async def current_member(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> team.Member:
    """The signed-in person and their role in the account their session is in,
    or 401; 403 when the role is below what this route needs, when a cookie
    request that changes something lacks its CSRF token, or when the account
    requires two-factor and this session signed in without it."""
    token, via_cookie = request_token(request, creds)
    if not token:
        raise _UNAUTH
    m, sess = await member_from_token(db, token)
    if via_cookie and request.method.upper() not in roles.READ:
        if not sessions.check_csrf(sess.id, request.headers.get("x-csrf-token")):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "csrf_failed")
    path = _route_path(request)
    if m.require_mfa and not sess.mfa and not path.startswith(_MFA_SETUP_PATHS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "mfa_setup_required")
    needed = roles.required_role(request.method, path)
    if not roles.at_least(m.role, needed):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Your role ({m.role}) can't do this; it needs {needed}.")
    request.state.member = m   # read by the audit log middleware
    return m


async def current_tenant(m: team.Member = Depends(current_member)) -> store.Tenant:
    """The account the signed-in member acts in (role already checked)."""
    return m.tenant
