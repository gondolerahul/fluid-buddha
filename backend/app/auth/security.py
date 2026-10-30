"""
Password hashing (bcrypt) + JWT bearer tokens + the ``current_tenant`` FastAPI
dependency that guards every tenant-scoped route (req A).

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
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
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
def create_access_token(tenant_id: uuid.UUID, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(tenant_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_min)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---- dependency -----------------------------------------------------------
_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_tenant(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> store.Tenant:
    """Resolve the authenticated tenant from the ``Authorization: Bearer`` token,
    or raise 401. Use as ``tenant: Tenant = Depends(current_tenant)``."""
    if creds is None or not creds.credentials:
        raise _UNAUTH
    try:
        payload = decode_token(creds.credentials)
        tenant_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTH
    tenant = await store.get_tenant(db, tenant_id)
    if tenant is None:
        raise _UNAUTH
    return tenant
