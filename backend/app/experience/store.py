"""
Storage for console-managed experience configuration (P0-7).

* ``site_design_systems`` — one current design system per site.
* ``site_component_manifests`` — manifest versions: ``draft`` → ``approved``
  (by an Admin) → ``archived`` (when a newer version is approved). Approved
  and archived versions are immutable; only drafts can be deleted.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SOURCES = ("manual", "storybook", "site", "file")


def _row(r: Any) -> dict[str, Any]:
    m = dict(r._mapping)
    m["id"] = str(m["id"])
    for k in ("created_at", "approved_at"):
        if m.get(k) is not None:
            m[k] = m[k].isoformat()
    return m


# ---- design systems ---------------------------------------------------------

async def get_design_system(db: AsyncSession, site_key: str) -> Optional[dict[str, Any]]:
    row = (await db.execute(
        text("SELECT data, updated_at, updated_by FROM site_design_systems WHERE site_key = :sk"),
        {"sk": site_key},
    )).first()
    if row is None:
        return None
    return {"data": row.data, "updated_at": row.updated_at.isoformat(), "updated_by": row.updated_by}


async def put_design_system(
    db: AsyncSession, site_key: str, data: dict[str, Any], actor: Optional[str],
) -> None:
    await db.execute(text("""
        INSERT INTO site_design_systems (site_key, data, updated_by)
        VALUES (:sk, CAST(:d AS jsonb), :by)
        ON CONFLICT (site_key) DO UPDATE
           SET data = EXCLUDED.data, updated_at = now(), updated_by = EXCLUDED.updated_by
    """), {"sk": site_key, "d": json.dumps(data), "by": actor})
    await db.commit()


async def delete_design_system(db: AsyncSession, site_key: str) -> bool:
    res = await db.execute(text("DELETE FROM site_design_systems WHERE site_key = :sk"),
                           {"sk": site_key})
    await db.commit()
    return (res.rowcount or 0) > 0


# ---- manifest versions ------------------------------------------------------

_COLS = ("id, site_key, version, status, source, notes, created_at, created_by, "
         "approved_at, approved_by")


async def list_versions(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        f"SELECT {_COLS}, jsonb_array_length(COALESCE(data->'components', '[]'::jsonb)) AS components "
        "FROM site_component_manifests WHERE site_key = :sk ORDER BY version DESC"),
        {"sk": site_key})).all()
    return [_row(r) for r in rows]


async def get_version(db: AsyncSession, site_key: str, version: int) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(
        f"SELECT {_COLS}, data FROM site_component_manifests "
        "WHERE site_key = :sk AND version = :v"), {"sk": site_key, "v": version})).first()
    return _row(row) if row else None


async def approved_manifest(db: AsyncSession, site_key: str) -> Optional[dict[str, Any]]:
    row = (await db.execute(text(
        f"SELECT {_COLS}, data FROM site_component_manifests "
        "WHERE site_key = :sk AND status = 'approved'"), {"sk": site_key})).first()
    return _row(row) if row else None


async def create_version(
    db: AsyncSession, site_key: str, data: dict[str, Any], *,
    source: str = "manual", notes: str = "", actor: Optional[str] = None,
) -> dict[str, Any]:
    source = source if source in SOURCES else "manual"
    # Serialise version numbering per site (a unique key backs this up).
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                     {"k": f"manifest:{site_key}"})
    nxt = (await db.execute(text(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM site_component_manifests WHERE site_key = :sk"),
        {"sk": site_key})).scalar_one()
    await db.execute(text("""
        INSERT INTO site_component_manifests (id, site_key, version, status, source, data, notes, created_by)
        VALUES (:id, :sk, :v, 'draft', :src, CAST(:d AS jsonb), :notes, :by)
    """), {"id": uuid.uuid4(), "sk": site_key, "v": nxt, "src": source,
           "d": json.dumps(data), "notes": notes[:1000], "by": actor})
    await db.commit()
    created = await get_version(db, site_key, nxt)
    assert created is not None
    return created


async def update_draft(
    db: AsyncSession, site_key: str, version: int, data: dict[str, Any], notes: str,
) -> bool:
    res = await db.execute(text(
        "UPDATE site_component_manifests SET data = CAST(:d AS jsonb), notes = :n "
        "WHERE site_key = :sk AND version = :v AND status = 'draft'"),
        {"d": json.dumps(data), "n": notes[:1000], "sk": site_key, "v": version})
    await db.commit()
    return (res.rowcount or 0) > 0


async def approve_version(
    db: AsyncSession, site_key: str, version: int, actor: Optional[str],
) -> Optional[dict[str, Any]]:
    """Approve a draft and archive the previously approved version. Returns
    None when the version does not exist or is not a draft."""
    cur = await get_version(db, site_key, version)
    if cur is None or cur["status"] != "draft":
        return None
    await db.execute(text(
        "UPDATE site_component_manifests SET status = 'archived' "
        "WHERE site_key = :sk AND status = 'approved'"), {"sk": site_key})
    await db.execute(text(
        "UPDATE site_component_manifests SET status = 'approved', approved_at = now(), "
        "approved_by = :by WHERE site_key = :sk AND version = :v"),
        {"sk": site_key, "v": version, "by": actor})
    await db.commit()
    return await get_version(db, site_key, version)


async def delete_draft(db: AsyncSession, site_key: str, version: int) -> bool:
    res = await db.execute(text(
        "DELETE FROM site_component_manifests WHERE site_key = :sk AND version = :v "
        "AND status = 'draft'"), {"sk": site_key, "v": version})
    await db.commit()
    return (res.rowcount or 0) > 0
