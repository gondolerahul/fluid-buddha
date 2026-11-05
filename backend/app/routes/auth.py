"""
Sign-up, sign-in and the signed-in person's accounts (req A, M2-1), with the
security controls of M2-11.

    POST /auth/register                 a new account, you as its Owner
    POST /auth/login                    email + password → a session, or a
                                        two-factor challenge {mfa_required, mfa_token}
    POST /auth/login/mfa                {mfa_token, code | recovery_code} → a session
    POST /auth/logout                   end this session
    GET  /auth/me                       you, your role, the account, the CSRF token
    GET  /auth/accounts                 every account you belong to
    POST /auth/switch                   {tenant_id} → a session in that account
    GET  /auth/sessions                 your live sessions
    DELETE /auth/sessions/{id}          end one of them
    POST /auth/sessions/revoke-others   sign out everywhere else
    POST /auth/password                 {current_password, new_password}
    GET  /auth/mfa                      two-factor status
    POST /auth/mfa/setup                a new secret to scan (not active yet)
    POST /auth/mfa/enable               {code} → on; recovery codes shown once
    POST /auth/mfa/disable              {code, password}
    POST /auth/mfa/recovery-codes       {code} → a fresh set
    GET  /auth/invitations/{token}      what an invitation is for (no sign-in)
    POST /auth/invitations/{token}/accept

A session is a row in ``user_sessions`` with idle and absolute timeouts
(``app.auth.sessions``). Every sign-in returns the token in the body (API
clients send it as a bearer) and sets it as an httpOnly cookie (the console);
cookie requests that change something carry ``X-CSRF-Token``. Wrong passwords
or codes ``LOGIN_MAX_ATTEMPTS`` times in a row lock the person out for
``LOGIN_LOCKOUT_MINUTES``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import mfa, sessions, team
from app.auth.security import (
    create_access_token,
    current_member,
    decode_token,
    hash_password,
    member_from_token,
    request_token,
    verify_password,
)
from app.config import get_settings
from app.db import get_session
from app.security import secrets as stored

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


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
    csrf_token: str | None = None
    expires_at: str | None = None


async def start_session(db: AsyncSession, m: team.Member, request: Request, response: Response,
                        method: str) -> TokenResponse:
    """A new session for ``m``: the token in the body and in the cookie."""
    sess = await sessions.start(db, user_id=m.user_id, tenant_id=m.tenant.id, method=method,
                                request=request)
    await db.commit()
    token = create_access_token(m.user_id, m.tenant.id, session_id=sess.id,
                                expires_at=sess.expires_at)
    sessions.set_cookie(response, token)
    return TokenResponse(access_token=token, tenant=m.tenant.public(), role=m.role,
                         user={"id": str(m.user_id), "email": m.email, "name": m.name},
                         csrf_token=sessions.csrf_for(sess.id),
                         expires_at=sess.expires_at.isoformat())


_BAD_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")


# ---- lockout ----------------------------------------------------------------------------

async def _user(db: AsyncSession, *, email: str | None = None,
                user_id: uuid.UUID | None = None) -> Optional[dict]:
    row = (await db.execute(text(
        "SELECT id, email, name, password_hash, totp_secret_enc, totp_pending_enc, "
        "totp_enabled_at, totp_last_step, recovery_codes, failed_attempts, locked_until "
        "FROM users WHERE " + ("email = :v" if email else "id = :v")),
        {"v": email.strip().lower() if email else user_id})).mappings().first()
    return dict(row) if row else None


def _locked(user: dict) -> Optional[HTTPException]:
    until = user.get("locked_until")
    if until and until > datetime.now(timezone.utc):
        minutes = max(1, int((until - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                             f"Too many attempts. Try again in {minutes} minute"
                             f"{'' if minutes == 1 else 's'}.")
    return None


async def _failed(db: AsyncSession, user: dict) -> bool:
    """Count a wrong password or code; True when this one locked the person out."""
    s = get_settings()
    n = (user.get("failed_attempts") or 0) + 1
    lock = n >= s.login_max_attempts
    await db.execute(text(
        "UPDATE users SET failed_attempts = :n, locked_until = :until WHERE id = :id"),
        {"n": 0 if lock else n, "id": user["id"],
         "until": datetime.now(timezone.utc) + timedelta(minutes=s.login_lockout_minutes)
         if lock else None})
    return lock


async def _succeeded(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(text(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = now() "
        "WHERE id = :id"), {"id": user_id})


# ---- sign-up / sign-in ------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, response: Response,
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
    return await start_session(db, m, request, response, "password")


async def _sso_required(db: AsyncSession, m: team.Member) -> bool:
    """An account that requires SSO refuses passwords from its domains (the
    Owner keeps password access, so a broken IdP can't lock everyone out)."""
    if m.role == "owner":
        return False
    return bool((await db.execute(text(
        "SELECT 1 FROM tenant_sso s JOIN sso_domains d ON d.tenant_id = s.tenant_id "
        "WHERE s.tenant_id = :t AND s.enabled AND s.require_sso AND d.verified_at IS NOT NULL "
        "AND d.domain = :d"), {"t": m.tenant.id, "d": m.email.rpartition("@")[2]})).first())


_MFA_TOKEN_MINUTES = 5


def _mfa_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "purpose": "mfa", "iat": int(now.timestamp()),
                       "exp": int((now + timedelta(minutes=_MFA_TOKEN_MINUTES)).timestamp())},
                      s.jwt_secret, algorithm=s.jwt_algorithm)


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response,
                db: AsyncSession = Depends(get_session)):
    user = await _user(db, email=body.email)
    if user is not None and (lock := _locked(user)):
        raise lock
    if (user is None or not user["password_hash"]
            or not verify_password(body.password, user["password_hash"])):
        if user is not None:
            locked = await _failed(db, user) if user["password_hash"] else False
            m = await team.member(db, user["id"], None)
            await audit.record(db, action="login.failed", tenant_id=m.tenant.id if m else None,
                               actor_user_id=user["id"], actor_email=user["email"],
                               details={"locked": True} if locked else None,
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
    if user["totp_enabled_at"] is not None:
        # The password was right; the code comes next (no session yet).
        await db.execute(text("UPDATE users SET failed_attempts = 0 WHERE id = :id"),
                         {"id": user["id"]})
        await db.commit()
        return {"mfa_required": True, "mfa_token": _mfa_token(user["id"])}
    await _succeeded(db, m.user_id)
    await audit.record(db, action="login", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, details={"method": "password"},
                       **audit.request_meta(request))
    return await start_session(db, m, request, response, "password")


class MFALoginRequest(BaseModel):
    mfa_token: str
    code: str | None = Field(None, max_length=12)
    recovery_code: str | None = Field(None, max_length=20)


@router.post("/login/mfa", response_model=TokenResponse)
async def login_mfa(body: MFALoginRequest, request: Request, response: Response,
                    db: AsyncSession = Depends(get_session)):
    try:
        claims = decode_token(body.mfa_token)
        if claims.get("purpose") != "mfa":
            raise ValueError
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "That sign-in took too long. Enter your password again.")
    user = await _user(db, user_id=user_id)
    if user is None or user["totp_enabled_at"] is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Enter your password again.")
    if lock := _locked(user):
        raise lock
    used = None
    if body.recovery_code:
        left = mfa.use_recovery_code(body.recovery_code, list(user["recovery_codes"] or []))
        if left is not None:
            used = "recovery_code"
            await db.execute(text(
                "UPDATE users SET recovery_codes = CAST(:c AS jsonb) WHERE id = :id"),
                {"c": _json(left), "id": user_id})
    elif body.code:
        step = mfa.verify(stored.decrypt(user["totp_secret_enc"]), body.code,
                          last_step=user["totp_last_step"])
        if step is not None:
            used = "totp"
            await db.execute(text("UPDATE users SET totp_last_step = :s WHERE id = :id"),
                             {"s": step, "id": user_id})
    m = await team.member(db, user_id, None)
    if used is None or m is None:
        await _failed(db, user)
        await audit.record(db, action="login.failed", tenant_id=m.tenant.id if m else None,
                           actor_user_id=user_id, actor_email=user["email"],
                           details={"step": "two-factor"}, **audit.request_meta(request))
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code isn't right.")
    await _succeeded(db, user_id)
    await audit.record(db, action="login", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, details={"method": "password+totp", "factor": used},
                       **audit.request_meta(request))
    return await start_session(db, m, request, response, "password+totp")


def _json(v) -> str:
    import json
    return json.dumps(v)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request,
                 creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                 db: AsyncSession = Depends(get_session)):
    """Ends this session (even one that already timed out) and clears the cookie."""
    token, _ = request_token(request, creds)
    try:
        claims = decode_token(token) if token else {}
        sid = uuid.UUID(claims["sid"]) if claims.get("sid") else None
    except (jwt.PyJWTError, ValueError):
        sid = None
    if sid:
        await sessions.revoke(db, sid)
        await db.commit()
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    sessions.clear_cookie(out)
    return out


@router.get("/me")
async def me(m: team.Member = Depends(current_member),
             db: AsyncSession = Depends(get_session)) -> dict:
    s = get_settings()
    # The account's fields stay at the top level for older console builds.
    return {**m.tenant.public(), "role": m.role,
            "user": {"id": str(m.user_id), "email": m.email, "name": m.name},
            "csrf_token": sessions.csrf_for(m.session_id) if m.session_id else None,
            "security": {"mfa_enabled": m.mfa_enabled, "mfa_required": m.require_mfa,
                         "session_mfa": m.session_mfa,
                         "mfa_setup_required": m.require_mfa and not m.session_mfa,
                         "idle_minutes": s.session_idle_minutes}}


@router.get("/accounts")
async def my_accounts(m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> list[dict]:
    return await team.accounts(db, m.user_id)


class SwitchRequest(BaseModel):
    tenant_id: uuid.UUID


@router.post("/switch", response_model=TokenResponse)
async def switch(body: SwitchRequest, request: Request, response: Response,
                 m: team.Member = Depends(current_member),
                 db: AsyncSession = Depends(get_session)):
    other = await team.member(db, m.user_id, body.tenant_id)
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You aren't a member of that account.")
    # The new session keeps how this one signed in (a second factor carries over);
    # the old one stays valid until it times out (API clients may still hold it).
    method = (await db.execute(text("SELECT method FROM user_sessions WHERE id = :id"),
                               {"id": m.session_id})).scalar_one()
    return await start_session(db, other, request, response, method)


# ---- sessions and password -----------------------------------------------------------

@router.get("/sessions")
async def my_sessions(m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> dict:
    return {"current": str(m.session_id), "sessions": await sessions.list_for(db, m.user_id)}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: uuid.UUID, request: Request,
                      m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> None:
    res = await db.execute(text(
        "UPDATE user_sessions SET revoked_at = now() WHERE id = :id AND user_id = :u "
        "AND revoked_at IS NULL"), {"id": session_id, "u": m.user_id})
    if not res.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such session.")
    await audit.record(db, action="session.revoke", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, target_type="session", target_id=str(session_id),
                       **audit.request_meta(request))
    await db.commit()


@router.post("/sessions/revoke-others")
async def revoke_others(request: Request, m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> dict:
    n = await sessions.revoke_all(db, m.user_id, keep=m.session_id)
    await audit.record(db, action="session.revoke_others", tenant_id=m.tenant.id,
                       actor_user_id=m.user_id, actor_email=m.email, details={"ended": n},
                       **audit.request_meta(request))
    await db.commit()
    return {"ended": n}


class PasswordChange(BaseModel):
    current_password: str | None = Field(None, max_length=256)
    new_password: str = Field(..., min_length=8, max_length=256)


@router.post("/password")
async def change_password(body: PasswordChange, request: Request,
                          m: team.Member = Depends(current_member),
                          db: AsyncSession = Depends(get_session)) -> dict:
    """Set a new password; every other session ends. A person who only ever
    used SSO can set a first password (if their account allows passwords)."""
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    if user["password_hash"] and not verify_password(body.current_password or "",
                                                     user["password_hash"]):
        await _failed(db, user)
        await db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password isn't right.")
    await db.execute(text(
        "UPDATE users SET password_hash = :p, password_changed_at = now(), failed_attempts = 0 "
        "WHERE id = :id"), {"p": hash_password(body.new_password), "id": m.user_id})
    ended = await sessions.revoke_all(db, m.user_id, keep=m.session_id)
    await audit.record(db, action="password.change", tenant_id=m.tenant.id,
                       actor_user_id=m.user_id, actor_email=m.email,
                       details={"other_sessions_ended": ended}, **audit.request_meta(request))
    await db.commit()
    return {"changed": True, "other_sessions_ended": ended}


# ---- two-factor ---------------------------------------------------------------------------

class CodeIn(BaseModel):
    code: str = Field(..., max_length=20)


class DisableIn(BaseModel):
    code: str = Field(..., max_length=20)
    password: str | None = Field(None, max_length=256)


@router.get("/mfa")
async def mfa_status(m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> dict:
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    return {"enabled": user["totp_enabled_at"] is not None,
            "enabled_at": user["totp_enabled_at"].isoformat() if user["totp_enabled_at"] else None,
            "required": m.require_mfa,
            "recovery_codes_left": len(user["recovery_codes"] or [])}


@router.post("/mfa/setup")
async def mfa_setup(m: team.Member = Depends(current_member),
                    db: AsyncSession = Depends(get_session)) -> dict:
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    if user["totp_enabled_at"] is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-factor is already on.")
    secret = mfa.new_secret()
    await db.execute(text("UPDATE users SET totp_pending_enc = :s WHERE id = :id"),
                     {"s": stored.encrypt(secret), "id": m.user_id})
    await db.commit()
    return {"secret": secret, "otpauth_uri": mfa.otpauth_uri(secret, m.email)}


async def _check_code(db: AsyncSession, user: dict, code: str) -> bool:
    """A current TOTP code (marked used) or a recovery code (used up)."""
    if user["totp_secret_enc"]:
        step = mfa.verify(stored.decrypt(user["totp_secret_enc"]), code,
                          last_step=user["totp_last_step"])
        if step is not None:
            await db.execute(text("UPDATE users SET totp_last_step = :s WHERE id = :id"),
                             {"s": step, "id": user["id"]})
            return True
    left = mfa.use_recovery_code(code, list(user["recovery_codes"] or []))
    if left is not None:
        await db.execute(text("UPDATE users SET recovery_codes = CAST(:c AS jsonb) WHERE id = :id"),
                         {"c": _json(left), "id": user["id"]})
        return True
    return False


@router.post("/mfa/enable")
async def mfa_enable(body: CodeIn, request: Request, m: team.Member = Depends(current_member),
                     db: AsyncSession = Depends(get_session)) -> dict:
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    if user["totp_enabled_at"] is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-factor is already on.")
    if not user["totp_pending_enc"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start the setup first.")
    secret = stored.decrypt(user["totp_pending_enc"])
    step = mfa.verify(secret, body.code)
    if step is None:
        await _failed(db, user)
        await db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "That code isn't right. Check your phone's clock and try the newest code.")
    codes, hashes = mfa.new_recovery_codes()
    await db.execute(text(
        "UPDATE users SET totp_secret_enc = :s, totp_pending_enc = NULL, totp_enabled_at = now(), "
        "totp_last_step = :step, recovery_codes = CAST(:c AS jsonb) WHERE id = :id"),
        {"s": user["totp_pending_enc"], "step": step, "c": _json(hashes), "id": m.user_id})
    # This session has now shown a second factor.
    await sessions.set_method(db, m.session_id, "password+totp")
    await audit.record(db, action="mfa.enable", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, **audit.request_meta(request))
    await db.commit()
    return {"enabled": True, "recovery_codes": codes}


@router.post("/mfa/disable")
async def mfa_disable(body: DisableIn, request: Request, m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> dict:
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    if user["totp_enabled_at"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-factor is already off.")
    if m.require_mfa:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your account requires two-factor, so it can't be switched off.")
    if user["password_hash"] and not verify_password(body.password or "", user["password_hash"]):
        await _failed(db, user)
        await db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your password isn't right.")
    if not await _check_code(db, user, body.code):
        await _failed(db, user)
        await db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That code isn't right.")
    await db.execute(text(
        "UPDATE users SET totp_secret_enc = NULL, totp_pending_enc = NULL, totp_enabled_at = NULL, "
        "totp_last_step = NULL, recovery_codes = '[]'::jsonb WHERE id = :id"), {"id": m.user_id})
    await audit.record(db, action="mfa.disable", tenant_id=m.tenant.id, actor_user_id=m.user_id,
                       actor_email=m.email, **audit.request_meta(request))
    await db.commit()
    return {"enabled": False}


@router.post("/mfa/recovery-codes")
async def mfa_new_codes(body: CodeIn, request: Request, m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> dict:
    user = await _user(db, user_id=m.user_id)
    assert user is not None
    if user["totp_enabled_at"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-factor is off.")
    if not await _check_code(db, user, body.code):
        await _failed(db, user)
        await db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That code isn't right.")
    codes, hashes = mfa.new_recovery_codes()
    await db.execute(text("UPDATE users SET recovery_codes = CAST(:c AS jsonb) WHERE id = :id"),
                     {"c": _json(hashes), "id": m.user_id})
    await audit.record(db, action="mfa.recovery_codes", tenant_id=m.tenant.id,
                       actor_user_id=m.user_id, actor_email=m.email, **audit.request_meta(request))
    await db.commit()
    return {"recovery_codes": codes}


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


@router.post("/invitations/{token}/accept", response_model=TokenResponse)
async def accept_invitation(
    token: str, body: AcceptRequest, request: Request, response: Response,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
):
    inv = await team.invitation_by_token(db, token)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "This invitation has expired or was already used.")
    user = await team.user_by_email(db, inv["email"])
    method = "password"
    if user is not None:
        # An existing person proves who they are by being signed in as them.
        signed_in = None
        bearer, _ = request_token(request, creds)
        if bearer:
            try:
                current, sess = await member_from_token(db, bearer)
                signed_in, method = current.user_id, sess.method
            except HTTPException:
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
    return await start_session(db, m, request, response, method)
