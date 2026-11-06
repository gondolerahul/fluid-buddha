"""
Audit log (M2-1, SOC 2 evidence): who changed what, when, from where.

Two ways in:

* **Every successful change through the console API** is recorded by
  ``AuditMiddleware``: any non-read request to ``/tenant/…`` made by a signed-in
  member that ends in a 2xx. The action is the route's endpoint name (e.g.
  ``put_integrations``), the target is the route's ids. Request bodies are not
  stored (they can hold secrets and visitor data). New routes are covered
  without any extra code.
* **Events the middleware can't see** — sign-ins (and failed ones), sign-ups,
  accepting an invitation, SSO — call ``record`` directly.

Rows are append-only; ``purge_old`` drops them after ``RETENTION_DAYS``.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.context import request_id

logger = logging.getLogger(__name__)

RETENTION_DAYS = 365
_READ = {"GET", "HEAD", "OPTIONS"}


def _header(scope: Scope, name: bytes) -> Optional[str]:
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            return v.decode("latin-1", errors="replace")[:300]
    return None


def _client_ip(scope: Scope) -> Optional[str]:
    fwd = _header(scope, b"x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    client = scope.get("client")
    return client[0] if client else None


async def record(db: AsyncSession, *, action: str, tenant_id: Optional[uuid.UUID],
                 actor_user_id: Optional[uuid.UUID] = None, actor_email: Optional[str] = None,
                 target_type: Optional[str] = None, target_id: Optional[str] = None,
                 details: Optional[dict[str, Any]] = None, ip: Optional[str] = None,
                 user_agent: Optional[str] = None) -> None:
    """Add one entry (part of the caller's transaction)."""
    await db.execute(text(
        "INSERT INTO audit_events (tenant_id, actor_user_id, actor_email, action, target_type, "
        "target_id, details, ip, user_agent, request_id) VALUES (:t, :u, :e, :a, :tt, :ti, "
        "CAST(:d AS jsonb), :ip, :ua, :rid)"),
        {"t": tenant_id, "u": actor_user_id, "e": actor_email, "a": action, "tt": target_type,
         "ti": target_id, "d": json.dumps(details or {}, default=str), "ip": ip,
         "ua": user_agent, "rid": request_id.get()})


def request_meta(request) -> dict[str, Optional[str]]:
    """``ip`` and ``user_agent`` of a FastAPI request, for ``record``."""
    return {"ip": _client_ip(request.scope), "user_agent": _header(request.scope, b"user-agent")}


async def search(db: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 100,
                 before: Optional[int] = None, action: Optional[str] = None,
                 actor: Optional[str] = None) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, actor_email, action, target_type, target_id, details, ip, user_agent, "
        "request_id, at FROM audit_events WHERE tenant_id = :t "
        "AND (CAST(:b AS bigint) IS NULL OR id < :b) "
        "AND (CAST(:a AS text) IS NULL OR action ILIKE '%' || :a || '%') "
        "AND (CAST(:e AS text) IS NULL OR actor_email ILIKE '%' || :e || '%') "
        "ORDER BY id DESC LIMIT :n"),
        {"t": tenant_id, "b": before, "a": action, "e": actor, "n": limit})).mappings().all()
    out = []
    for r in rows:
        d = r["details"]
        out.append({**dict(r), "details": json.loads(d) if isinstance(d, str) else d,
                    "at": r["at"].isoformat()})
    return out


async def purge_old(db: AsyncSession) -> int:
    n = (await db.execute(text(
        "DELETE FROM audit_events WHERE at < now() - make_interval(days => :d)"),
        {"d": RETENTION_DAYS})).rowcount
    await db.commit()
    return n or 0


class AuditMiddleware:
    """Records successful changes made through ``/tenant`` routes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (scope["type"] != "http" or scope.get("method") in _READ
                or not scope.get("path", "").startswith("/tenant")):
            await self.app(scope, receive, send)
            return
        status_holder: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        member = (scope.get("state") or {}).get("member")
        status = status_holder.get("status", 500)
        if member is None or not 200 <= status < 300:
            return
        route = scope.get("route")
        endpoint = scope.get("endpoint")
        params = {k: str(v) for k, v in (scope.get("path_params") or {}).items()}
        target_type, target_id = None, None
        if params:
            target_type, target_id = next(reversed(params.items()))
            target_type = target_type.removesuffix("_id")
        try:
            from app.db import session_scope

            async with session_scope() as db:
                await record(
                    db, action=getattr(endpoint, "__name__", None) or scope["method"].lower(),
                    tenant_id=member.tenant.id, actor_user_id=member.user_id,
                    actor_email=member.email, target_type=target_type, target_id=target_id,
                    details={"method": scope["method"],
                             "route": getattr(route, "path", scope.get("path")),
                             "params": params, "status": status, "role": member.role},
                    ip=_client_ip(scope), user_agent=_header(scope, b"user-agent"))
        except Exception:   # the change already happened; never fail the response
            logger.exception("audit record failed for %s", scope.get("path"))
