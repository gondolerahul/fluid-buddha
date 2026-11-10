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
              token_id: Optional[uuid.UUID] = None, ok: bool = True, error: Optional[str] = None,
              plan_id: Optional[str] = None, action: Optional[str] = None) -> None:
    await db.execute(text(
        "INSERT INTO agent_requests (site_key, kind, tool, client, token_id, ok, error, plan_id, action) "
        "VALUES (:s, :k, :t, :c, :tok, :ok, :e, :p, :a)"),
        {"s": site_key, "k": kind, "t": tool, "c": (client or "")[:120] or None, "tok": token_id,
         "ok": ok, "e": (error or None) and error[:300], "p": (plan_id or None) and plan_id[:20],
         "a": (action or None) and action[:60]})
    await db.commit()


READ_TOOLS = ("search_knowledge", "get_page", "list_offerings", "llms.txt", "ask", "offerings")
VIEW_TOOLS = ("get_view", "list_views")


async def funnel(db: AsyncSession, site_key: str, days: int = 30) -> dict[str, Any]:
    """Task completion (Phase 5): how many agent clients read the site, opened a
    view, started an action and completed one; where they failed; their leads."""
    p = {"s": site_key, "d": days}
    window = "site_key = :s AND at > now() - make_interval(days => :d)"
    rows = (await db.execute(text(
        f"SELECT coalesce(client, 'unknown') AS client, "
        f"bool_or(tool = ANY(:read)) AS read, bool_or(tool = ANY(:view)) AS viewed, "
        f"bool_or(tool LIKE 'view_action.%%') AS started, bool_or(tool = 'view_action.done') AS completed "
        f"FROM agent_requests WHERE {window} GROUP BY 1"),
        {**p, "read": list(READ_TOOLS), "view": list(VIEW_TOOLS)})).mappings().all()
    steps = {k: sum(1 for r in rows if r[k]) for k in ("read", "viewed", "started", "completed")}
    fails = (await db.execute(text(
        f"SELECT coalesce(plan_id, '') AS plan_id, coalesce(action, '') AS action, coalesce(tool, kind) AS tool, "
        f"count(*) AS n, max(error) AS error FROM agent_requests WHERE {window} AND NOT ok "
        f"GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 10"), p)).mappings().all()
    try:
        leads = int((await db.execute(text(
            "SELECT count(*) FROM leads WHERE site_key = :s AND source = 'agent' "
            "AND created_at > now() - make_interval(days => :d)"), p)).scalar() or 0)
    except Exception:
        await db.rollback()
        leads = 0
    return {"clients": len(rows), **steps, "leads": leads,
            "failures": [{"plan_id": r["plan_id"] or None, "action": r["action"] or None, "tool": r["tool"],
                          "count": int(r["n"]), "error": r["error"]} for r in fails]}


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
