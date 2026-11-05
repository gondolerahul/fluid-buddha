"""
Agent access: the site's switch, customer-issued tokens, and the traffic log (M3-2).

Tokens (``fbat_…``) are shown once and stored as a SHA-256 hash, scoped to one
site and to what they allow: ``leads`` (capture a lead) and ``actions`` (run
the site's actions). Reading — questions, pages, offerings — needs only the
site's public widget key.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SCOPES = ("leads", "actions")
PREFIX = "fbat_"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def site_for_key(db: AsyncSession, key: str) -> Optional[dict[str, Any]]:
    """The website a public widget key belongs to, with its agent-access switch."""
    row = (await db.execute(text(
        "SELECT id, tenant_id, site_key, name, domain, intelligence, agent_access, public_key "
        "FROM tenant_websites WHERE public_key = :k"), {"k": key})).mappings().first()
    return dict(row) if row else None


async def create_token(db: AsyncSession, site_key: str, name: str, scopes: list[str],
                       created_by: Optional[uuid.UUID]) -> tuple[dict[str, Any], str]:
    token = PREFIX + secrets.token_urlsafe(32)
    row = (await db.execute(text(
        "INSERT INTO agent_tokens (id, site_key, name, token_hash, scopes, created_by) "
        "VALUES (:id, :s, :n, :h, :sc, :by) RETURNING id, name, scopes, created_at, last_used_at"),
        {"id": uuid.uuid4(), "s": site_key, "n": name, "h": _hash(token),
         "sc": [s for s in SCOPES if s in scopes], "by": created_by})).mappings().one()
    return _public(row), token


def _public(r: Any) -> dict[str, Any]:
    return {"id": str(r["id"]), "name": r["name"], "scopes": list(r["scopes"] or []),
            "created_at": r["created_at"].isoformat(),
            "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None}


async def list_tokens(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT id, name, scopes, created_at, last_used_at FROM agent_tokens "
        "WHERE site_key = :s AND revoked_at IS NULL ORDER BY created_at DESC"), {"s": site_key})).mappings().all()
    return [_public(r) for r in rows]


async def revoke_token(db: AsyncSession, site_key: str, token_id: uuid.UUID) -> bool:
    return bool((await db.execute(text(
        "UPDATE agent_tokens SET revoked_at = now() WHERE id = :id AND site_key = :s AND revoked_at IS NULL"),
        {"id": token_id, "s": site_key})).rowcount)


async def verify(db: AsyncSession, site_key: str, token: Optional[str]) -> Optional[dict[str, Any]]:
    """The live token for this site, or None (a token for another site is no token)."""
    if not token or not token.startswith(PREFIX):
        return None
    row = (await db.execute(text(
        "UPDATE agent_tokens SET last_used_at = now() WHERE token_hash = :h AND site_key = :s "
        "AND revoked_at IS NULL RETURNING id, name, scopes"), {"h": _hash(token), "s": site_key})).mappings().first()
    if row:
        await db.commit()
    return {"id": row["id"], "name": row["name"], "scopes": list(row["scopes"] or [])} if row else None


async def log(db: AsyncSession, site_key: str, *, kind: str, tool: Optional[str], client: Optional[str],
              token_id: Optional[uuid.UUID] = None, ok: bool = True, error: Optional[str] = None) -> None:
    await db.execute(text(
        "INSERT INTO agent_requests (site_key, kind, tool, client, token_id, ok, error) "
        "VALUES (:s, :k, :t, :c, :tok, :ok, :e)"),
        {"s": site_key, "k": kind, "t": tool, "c": (client or "")[:120] or None, "tok": token_id,
         "ok": ok, "e": (error or None) and error[:300]})
    await db.commit()


async def traffic(db: AsyncSession, site_key: str, days: int = 30) -> dict[str, Any]:
    p = {"s": site_key, "d": days}
    window = "site_key = :s AND at > now() - make_interval(days => :d)"
    by_tool = (await db.execute(text(
        f"SELECT coalesce(tool, kind) AS tool, count(*) AS n, count(*) FILTER (WHERE NOT ok) AS failed "
        f"FROM agent_requests WHERE {window} GROUP BY 1 ORDER BY 2 DESC"), p)).mappings().all()
    by_client = (await db.execute(text(
        f"SELECT coalesce(client, 'unknown') AS client, count(*) AS n FROM agent_requests WHERE {window} "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"), p)).mappings().all()
    recent = (await db.execute(text(
        "SELECT kind, tool, client, ok, error, at FROM agent_requests WHERE site_key = :s "
        "ORDER BY at DESC LIMIT 50"), p)).mappings().all()
    return {
        "days": days,
        "total": sum(int(r["n"]) for r in by_tool),
        "by_tool": [{"tool": r["tool"], "count": int(r["n"]), "failed": int(r["failed"])} for r in by_tool],
        "by_client": [{"client": r["client"], "count": int(r["n"])} for r in by_client],
        "recent": [{**dict(r), "at": r["at"].isoformat()} for r in recent],
    }
