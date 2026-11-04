"""
Sign-up, sign-in and the signed-in person's accounts (req A, M2-1).

    POST /auth/register                 a new account, you as its Owner
    POST /auth/login                    email + password → token (first account)
    GET  /auth/me                       you, your role and the current account
    GET  /auth/accounts                 every account you belong to
    POST /auth/switch                   {tenant_id} → a token for that account
    GET  /auth/invitations/{token}      what an invitation is for (no sign-in)
    POST /auth/invitations/{token}/accept
         new person: {name?, password}; existing person: send their token

Tokens are bearer JWTs naming the person and the account (``app.auth.security``).
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import team
from app.auth.security import (
    create_access_token,
    current_member,
    decode_token,
    hash_password,
    verify_password,
)
from app.db import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=256)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant: dict
    role: str = "owner"
    user: dict | None = None


def _token_response(m: team.Member) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(m.user_id, m.tenant.id),
                         tenant=m.tenant.public(), role=m.role,
                         user={"id": str(m.user_id), "email": m.email, "name": m.name})


_BAD_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request,
                   db: AsyncSession = Depends(get_session)):
    if await team.user_by_email(db, body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user_id, tenant_id = await team.create_account(
        db, email=body.email, password_hash=hash_password(body.password), name=body.name)
    await team.touch_login(db, user_id)
    await audit.record(db, action="account.register", tenant_id=tenant_id,
                       actor_user_id=user_id, actor_email=body.email.lower(),
                       **audit.request_meta(request))
    await db.commit()
    m = await team.member(db, user_id, tenant_id)
    assert m is not None
    logger.info("account registered: %s", m.email)
    return _token_response(m)


async def _sso_required(db: AsyncSession, m: team.Member) -> bool:
    """An account that requires SSO refuses passwords from its domains (the
    Owner keeps password access, so a broken IdP can't lock everyone out)."""
    if m.role == "owner":
        return False
    return bool((await db.execute(text(
        "SELECT 1 FROM tenant_sso s JOIN sso_domains d ON d.tenant_id = s.tenant_id "
        "WHERE s.tenant_id = :t AND s.enabled AND s.require_sso AND d.verified_at IS NOT NULL "
        "AND d.domain = :d"), {"t": m.tenant.id, "d": m.email.rpartition("@")[2]})).first())


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_session)):
    user = await team.user_by_email(db, body.email)
    if (user is None or not user["password_hash"]
            or not verify_password(body.password, user["password_hash"])):
        if user is not None:
            m = await team.member(db, user["id"], None)
            await audit.record(db, action="login.failed", tenant_id=m.tenant.id if m else None,
                               actor_user_id=user["id"], actor_email=user["email"],
                               **audit.request_meta(request))
            await db.commit()
        raise _BAD_LOGIN
    m = await team.member(db, user["id"], None)
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You aren't a member of any account any more.")
    if await _sso_required(db, m):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Your organisation requires single sign-on. Use “Sign in with SSO”.")
    await team.touch_login(db, m.user_id)
    await audit.record(db, action="login", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, details={"method": "password"},
                       **audit.request_meta(request))
    await db.commit()
    return _token_response(m)


@router.get("/me")
async def me(m: team.Member = Depends(current_member)) -> dict:
    # The account's fields stay at the top level for older console builds.
    return {**m.tenant.public(), "role": m.role,
            "user": {"id": str(m.user_id), "email": m.email, "name": m.name}}


@router.get("/accounts")
async def my_accounts(m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> list[dict]:
    return await team.accounts(db, m.user_id)


class SwitchRequest(BaseModel):
    tenant_id: uuid.UUID


@router.post("/switch", response_model=TokenResponse)
async def switch(body: SwitchRequest, m: team.Member = Depends(current_member),
                 db: AsyncSession = Depends(get_session)):
    other = await team.member(db, m.user_id, body.tenant_id)
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You aren't a member of that account.")
    return _token_response(other)


# ---- invitations ------------------------------------------------------------------

@router.get("/invitations/{token}")
async def invitation(token: str, db: AsyncSession = Depends(get_session)) -> dict:
    inv = await team.invitation_by_token(db, token)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "This invitation has expired or was already used.")
    return {"account": inv["account"] or inv["account_email"], "email": inv["email"],
            "role": inv["role"], "expires_at": inv["expires_at"].isoformat(),
            "has_user": await team.user_by_email(db, inv["email"]) is not None}


class AcceptRequest(BaseModel):
    name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, min_length=8, max_length=256)


_bearer = HTTPBearer(auto_error=False)


@router.post("/invitations/{token}/accept", response_model=TokenResponse)
async def accept_invitation(
    token: str, body: AcceptRequest, request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
):
    inv = await team.invitation_by_token(db, token)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "This invitation has expired or was already used.")
    user = await team.user_by_email(db, inv["email"])
    if user is not None:
        # An existing person proves who they are by being signed in as them.
        try:
            signed_in = uuid.UUID(decode_token(creds.credentials)["sub"]) if creds else None
        except Exception:
            signed_in = None
        if signed_in != user["id"]:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                f"Sign in as {inv['email']} first, then accept the invitation.")
        user_id = user["id"]
    else:
        if not body.password:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Choose a password (at least 8 characters).")
        user_id = await team.create_user(db, email=inv["email"], name=body.name,
                                         password_hash=hash_password(body.password))
    if not await team.mark_accepted(db, inv["id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "This invitation was already used.")
    await team.add_member(db, user_id, inv["tenant_id"], inv["role"])
    await team.touch_login(db, user_id)
    await audit.record(db, action="invitation.accept", tenant_id=inv["tenant_id"],
                       actor_user_id=user_id, actor_email=inv["email"],
                       target_type="invitation", target_id=str(inv["id"]),
                       details={"role": inv["role"]}, **audit.request_meta(request))
    await db.commit()
    m = await team.member(db, user_id, inv["tenant_id"])
    assert m is not None
    return _token_response(m)
