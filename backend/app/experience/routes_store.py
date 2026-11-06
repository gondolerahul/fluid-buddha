"""
Route registry (P2-5).

Composed pages are served for routes the owner registers. A pattern is a path
with optional parameters:

* ``/pricing``            — exact;
* ``/products/:slug``     — ``:name`` matches one segment, available to
  bindings as ``route.slug``;
* ``/guides/*``           — ``*`` matches the rest (``route.rest``).

When several patterns match, the more specific one wins (more literal
segments, then fewer wildcards, then the owner's priority).
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experience.regions_store import normalize_page

PATTERN_RE = re.compile(r"^/([a-z0-9._~-]+|:[a-z][a-z0-9_]{0,30})?(/([a-z0-9._~-]+|:[a-z][a-z0-9_]{0,30}))*(/\*)?$")
PAGE_REGIONS = "@page"


@dataclass
class Route:
    id: str
    pattern: str
    title: str = ""
    purpose: str = ""
    enabled: bool = True
    priority: int = 0
    canonical_plan: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "pattern": self.pattern, "title": self.title, "purpose": self.purpose,
                "enabled": self.enabled, "priority": self.priority, "canonical_plan": self.canonical_plan}

    def match(self, path: str) -> Optional[dict[str, str]]:
        return match_pattern(self.pattern, path)

    @property
    def specificity(self) -> tuple[int, int, int]:
        segs = [s for s in self.pattern.split("/") if s]
        literal = sum(1 for s in segs if not s.startswith(":") and s != "*")
        return (literal, -sum(1 for s in segs if s == "*"), self.priority)


def valid_pattern(p: str) -> bool:
    return p == "/" or bool(PATTERN_RE.match(p))


def match_pattern(pattern: str, path: str) -> Optional[dict[str, str]]:
    path = normalize_page(path)
    pseg = [s for s in pattern.split("/") if s]
    seg = [s for s in path.split("/") if s]
    params: dict[str, str] = {}
    for i, p in enumerate(pseg):
        if p == "*":
            params["rest"] = "/".join(seg[i:])
            return params
        if i >= len(seg):
            return None
        if p.startswith(":"):
            params[p[1:]] = seg[i]
        elif p != seg[i]:
            return None
    return params if len(seg) == len(pseg) else None


def _route(r: Any) -> Route:
    return Route(id=str(r.id), pattern=r.pattern, title=r.title, purpose=r.purpose, enabled=bool(r.enabled),
                 priority=r.priority, canonical_plan=str(r.canonical_plan) if r.canonical_plan else None)


_COLS = "id, pattern, title, purpose, enabled, priority, canonical_plan"


async def list_routes(db: AsyncSession, site_key: str) -> list[Route]:
    rows = (await db.execute(text(f"SELECT {_COLS} FROM site_routes WHERE site_key = :sk ORDER BY pattern"),
                             {"sk": site_key})).all()
    return [_route(r) for r in rows]


async def match_route(db: AsyncSession, site_key: str, path: str) -> Optional[tuple[Route, dict[str, str]]]:
    best: Optional[tuple[Route, dict[str, str]]] = None
    for r in await list_routes(db, site_key):
        if not r.enabled:
            continue
        params = r.match(path)
        if params is not None and (best is None or r.specificity > best[0].specificity):
            best = (r, params)
    return best


async def get_route(db: AsyncSession, site_key: str, rid: str) -> Optional[Route]:
    try:
        u = uuid.UUID(rid)
    except ValueError:
        return None
    r = (await db.execute(text(f"SELECT {_COLS} FROM site_routes WHERE site_key = :sk AND id = :id"),
                          {"sk": site_key, "id": u})).first()
    return _route(r) if r else None


async def upsert_route(db: AsyncSession, site_key: str, *, pattern: str, title: str, purpose: str,
                       enabled: bool, priority: int) -> Route:
    await db.execute(text("""
        INSERT INTO site_routes (id, site_key, pattern, title, purpose, enabled, priority)
        VALUES (:id, :sk, :p, :t, :pu, :e, :pr)
        ON CONFLICT (site_key, pattern) DO UPDATE SET title = EXCLUDED.title, purpose = EXCLUDED.purpose,
            enabled = EXCLUDED.enabled, priority = EXCLUDED.priority
    """), {"id": uuid.uuid4(), "sk": site_key, "p": pattern, "t": title, "pu": purpose, "e": enabled,
           "pr": priority})
    await db.commit()
    r = (await db.execute(text(f"SELECT {_COLS} FROM site_routes WHERE site_key = :sk AND pattern = :p"),
                          {"sk": site_key, "p": pattern})).first()
    return _route(r)


async def set_canonical(db: AsyncSession, site_key: str, rid: str, plan_row_id: Optional[str]) -> Optional[Route]:
    """Make a page plan the route's canonical page (served to crawlers and as the
    default). The plan is pinned so cache invalidation never removes it."""
    route = await get_route(db, site_key, rid)
    if route is None:
        return None
    pid = None
    if plan_row_id:
        from app.experience.regions_store import get_plan, set_plan_status

        row = await get_plan(db, site_key, plan_row_id)
        if row is None or row["status"] == "blocked" or row["regions"] != [PAGE_REGIONS] \
                or row["page"] != route.pattern:
            return None
        # Pinned the same way as "Pin": one pinned plan per goal and page.
        await set_plan_status(db, site_key, plan_row_id, "pinned")
        pid = uuid.UUID(plan_row_id)
    await db.execute(text("UPDATE site_routes SET canonical_plan = :p WHERE site_key = :sk AND id = :id"),
                     {"p": pid, "sk": site_key, "id": uuid.UUID(rid)})
    await db.commit()
    return await get_route(db, site_key, rid)


async def delete_route(db: AsyncSession, site_key: str, rid: str) -> bool:
    try:
        u = uuid.UUID(rid)
    except ValueError:
        return False
    res = await db.execute(text("DELETE FROM site_routes WHERE site_key = :sk AND id = :id"),
                           {"sk": site_key, "id": u})
    await db.commit()
    return (res.rowcount or 0) > 0
