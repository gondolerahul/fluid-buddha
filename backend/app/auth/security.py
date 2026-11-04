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
from app.auth import roles, team
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
                        settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_min)).timestamp()),
    }
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
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


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


async def current_member(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> team.Member:
    """The signed-in person and their role in the account the token names, or
    401; 403 when the role is below what this route needs. Tokens from before
    teams (no ``tid``) act in the user's first account — migrated owners keep
    the account's id as their user id."""
    if creds is None or not creds.credentials:
        raise _UNAUTH
    try:
        payload = decode_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tid"]) if payload.get("tid") else None
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTH
    m = await team.member(db, user_id, tenant_id)
    if m is None:
        raise _UNAUTH
    needed = roles.required_role(request.method, _route_path(request))
    if not roles.at_least(m.role, needed):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Your role ({m.role}) can't do this; it needs {needed}.")
    request.state.member = m   # read by the audit log middleware
    return m


async def current_tenant(m: team.Member = Depends(current_member)) -> store.Tenant:
    """The account the signed-in member acts in (role already checked)."""
    return m.tenant
