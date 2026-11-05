"""
People, their accounts and invitations (M2-1).

A **user** is a person (email, optional password — SSO-only users have none).
A **tenant** is an account (its websites, billing, settings). A
**membership** gives a user a role in a tenant. Signing up creates all three;
an invitation adds a membership to an existing account.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.roles import ROLES
from app.tenancy import store

INVITE_DAYS = 7


@dataclass
class Member:
    """The signed-in person acting in one account."""
    user_id: uuid.UUID
    email: str
    name: Optional[str]
    role: str
    tenant: store.Tenant
    # Security (M2-11): two-factor on for this person / required by the account,
    # and the session this request belongs to (set by current_member).
    mfa_enabled: bool = False
    require_mfa: bool = False
    session_id: Optional[uuid.UUID] = None
    session_mfa: bool = False

    def public(self) -> dict:
        return {"user": {"id": str(self.user_id), "email": self.email, "name": self.name},
                "role": self.role, "tenant": self.tenant.public()}


def _norm(email: str) -> str:
    return (email or "").strip().lower()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- users -----------------------------------------------------------------

async def user_by_email(db: AsyncSession, email: str) -> Optional[dict]:
    row = (await db.execute(text(
        "SELECT id, email, name, password_hash FROM users WHERE email = :e"),
        {"e": _norm(email)})).mappings().first()
    return dict(row) if row else None


async def create_user(db: AsyncSession, *, email: str, name: Optional[str],
                      password_hash: Optional[str]) -> uuid.UUID:
    uid = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO users (id, email, name, password_hash) VALUES (:id, :e, :n, :p)"),
        {"id": uid, "e": _norm(email), "n": name, "p": password_hash})
    return uid


async def touch_login(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(text("UPDATE users SET last_login_at = now() WHERE id = :id"),
                     {"id": user_id})


async def create_account(db: AsyncSession, *, email: str, password_hash: Optional[str],
                         name: Optional[str], user_id: Optional[uuid.UUID] = None,
                         ) -> tuple[uuid.UUID, uuid.UUID]:
    """Sign-up: a new account with this person as its Owner. Returns
    ``(user_id, tenant_id)``."""
    if user_id is None:
        user_id = await create_user(db, email=email, name=name, password_hash=password_hash)
    tenant_id = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO tenants (id, email, password_hash, name) VALUES (:id, :e, NULL, :n)"),
        {"id": tenant_id, "e": _norm(email), "n": name})
    await add_member(db, user_id, tenant_id, "owner")
    return user_id, tenant_id


# ---- memberships -------------------------------------------------------------

async def add_member(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID,
                     role: str) -> None:
    assert role in ROLES
    await db.execute(text(
        "INSERT INTO memberships (user_id, tenant_id, role) VALUES (:u, :t, :r) "
        "ON CONFLICT (user_id, tenant_id) DO NOTHING"),
        {"u": user_id, "t": tenant_id, "r": role})


async def member(db: AsyncSession, user_id: uuid.UUID,
                 tenant_id: Optional[uuid.UUID]) -> Optional[Member]:
    """The user's membership in ``tenant_id`` (or their oldest one)."""
    row = (await db.execute(text(
        "SELECT u.id AS user_id, u.email AS user_email, u.name AS user_name, m.role, "
        "u.totp_enabled_at IS NOT NULL AS mfa_enabled, t.require_mfa, "
        "t.id, t.email, t.name, t.created_at FROM memberships m "
        "JOIN users u ON u.id = m.user_id JOIN tenants t ON t.id = m.tenant_id "
        "WHERE m.user_id = :u AND (CAST(:t AS uuid) IS NULL OR m.tenant_id = :t) "
        "ORDER BY m.created_at LIMIT 1"), {"u": user_id, "t": tenant_id})).mappings().first()
    if not row:
        return None
    return Member(user_id=row["user_id"], email=row["user_email"], name=row["user_name"],
                  role=row["role"], tenant=store.Tenant(id=row["id"], email=row["email"],
                                                        name=row["name"],
                                                        created_at=row["created_at"]),
                  mfa_enabled=bool(row["mfa_enabled"]), require_mfa=bool(row["require_mfa"]))


async def accounts(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT t.id, t.name, t.email, m.role FROM memberships m JOIN tenants t "
        "ON t.id = m.tenant_id WHERE m.user_id = :u ORDER BY m.created_at"),
        {"u": user_id})).mappings().all()
    return [{"id": str(r["id"]), "name": r["name"] or r["email"], "role": r["role"]}
            for r in rows]


async def members(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT u.id, u.email, u.name, m.role, m.created_at, u.last_login_at, "
        "u.password_hash IS NOT NULL AS has_password, "
        "u.totp_enabled_at IS NOT NULL AS mfa_enabled FROM memberships m "
        "JOIN users u ON u.id = m.user_id WHERE m.tenant_id = :t ORDER BY m.created_at"),
        {"t": tenant_id})).mappings().all()
    return [{"id": str(r["id"]), "email": r["email"], "name": r["name"], "role": r["role"],
             "joined_at": r["created_at"].isoformat(),
             "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
             "mfa_enabled": bool(r["mfa_enabled"]),
             "has_password": r["has_password"]} for r in rows]


async def owner_count(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    return int((await db.execute(text(
        "SELECT count(*) FROM memberships WHERE tenant_id = :t AND role = 'owner'"),
        {"t": tenant_id})).scalar() or 0)


async def role_of(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
    return (await db.execute(text(
        "SELECT role FROM memberships WHERE tenant_id = :t AND user_id = :u"),
        {"t": tenant_id, "u": user_id})).scalar()


async def set_role(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                   role: str) -> None:
    await db.execute(text(
        "UPDATE memberships SET role = :r WHERE tenant_id = :t AND user_id = :u"),
        {"r": role, "t": tenant_id, "u": user_id})


async def remove_member(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(text("DELETE FROM memberships WHERE tenant_id = :t AND user_id = :u"),
                     {"t": tenant_id, "u": user_id})


# ---- invitations ---------------------------------------------------------------

async def invite(db: AsyncSession, tenant_id: uuid.UUID, email: str, role: str,
                 invited_by: uuid.UUID) -> tuple[uuid.UUID, str]:
    """A new invitation (older pending ones to the same address are revoked).
    Returns ``(id, token)``; only the token's hash is stored."""
    await db.execute(text(
        "UPDATE invitations SET revoked_at = now() WHERE tenant_id = :t AND email = :e "
        "AND accepted_at IS NULL AND revoked_at IS NULL"), {"t": tenant_id, "e": _norm(email)})
    token = secrets.token_urlsafe(32)
    iid = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO invitations (id, tenant_id, email, role, token_hash, invited_by, expires_at) "
        "VALUES (:id, :t, :e, :r, :h, :by, :exp)"),
        {"id": iid, "t": tenant_id, "e": _norm(email), "r": role, "h": hash_token(token),
         "by": invited_by,
         "exp": datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS)})
    return iid, token


async def pending_invitations(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT i.id, i.email, i.role, i.created_at, i.expires_at, u.email AS invited_by "
        "FROM invitations i LEFT JOIN users u ON u.id = i.invited_by "
        "WHERE i.tenant_id = :t AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
        "AND i.expires_at > now() ORDER BY i.created_at DESC"), {"t": tenant_id})).mappings().all()
    return [{"id": str(r["id"]), "email": r["email"], "role": r["role"],
             "invited_by": r["invited_by"], "created_at": r["created_at"].isoformat(),
             "expires_at": r["expires_at"].isoformat()} for r in rows]


async def invitation_by_token(db: AsyncSession, token: str) -> Optional[dict]:
    """A usable (pending, unexpired) invitation, with its account's name."""
    row = (await db.execute(text(
        "SELECT i.id, i.tenant_id, i.email, i.role, i.expires_at, t.name AS account, "
        "t.email AS account_email FROM invitations i JOIN tenants t ON t.id = i.tenant_id "
        "WHERE i.token_hash = :h AND i.accepted_at IS NULL AND i.revoked_at IS NULL "
        "AND i.expires_at > now()"), {"h": hash_token(token or "")})).mappings().first()
    return dict(row) if row else None


async def mark_accepted(db: AsyncSession, invitation_id: uuid.UUID) -> bool:
    res = await db.execute(text(
        "UPDATE invitations SET accepted_at = now() WHERE id = :id AND accepted_at IS NULL "
        "AND revoked_at IS NULL"), {"id": invitation_id})
    return bool(res.rowcount)


async def revoke_invitation(db: AsyncSession, tenant_id: uuid.UUID,
                            invitation_id: uuid.UUID) -> bool:
    res = await db.execute(text(
        "UPDATE invitations SET revoked_at = now() WHERE id = :id AND tenant_id = :t "
        "AND accepted_at IS NULL AND revoked_at IS NULL"), {"id": invitation_id, "t": tenant_id})
    return bool(res.rowcount)
