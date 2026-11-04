"""
Deletion for a site's knowledge and per-site state (docs/defects.md D-6).

``cortex_memory`` exposes ingest + search but no delete, so these run raw SQL
against its tables. The schema makes this safe: ``cortex_nodes.tree_id`` and
both ``cortex_edges`` node FKs are ``ON DELETE CASCADE``, so deleting a tree
removes its nodes and edges, and deleting a node removes its edges.

Every node built from a document carries ``source_ref.document_id``; tenant
sources are ingested with their own id as that document id, so a source's
knowledge can be removed precisely.
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import site_entity_id

# Per-site tables keyed by site_key (conversation_turns go with their
# conversation via ON DELETE CASCADE).
_SITE_TABLES = (
    "site_tours", "site_profiles", "conversation_cache", "answer_audio_cache", "usage_events",
    "conversations", "leads", "site_integrations", "site_privacy", "site_design",
    "experiments",  # its visitors and events go with it (ON DELETE CASCADE)
    "cost_alerts",
)


async def _table_exists(db: AsyncSession, table: str) -> bool:
    return bool((await db.execute(text("SELECT to_regclass(:t)"), {"t": table})).scalar())


async def delete_document_nodes(
    db: AsyncSession, site_key: str, document_id: uuid.UUID
) -> int:
    """Delete every CORTEX node built from ``document_id`` in this site's tree."""
    res = await db.execute(
        text(
            "DELETE FROM cortex_nodes WHERE tree_id IN "
            "(SELECT id FROM cortex_trees WHERE entity_id = :eid) "
            "AND source_ref->>'document_id' = :doc"
        ),
        {"eid": site_entity_id(site_key), "doc": str(document_id)},
    )
    return res.rowcount or 0


async def invalidate_site_caches(db: AsyncSession, site_key: str) -> None:
    """Drop cached answers + audio for a site after its knowledge changed.

    A replayed answer may quote content that was just deleted or replaced, so
    the replay caches are cleared rather than served stale. Pinned and blocked
    answers are the tenant's own decisions and stay (WS8).
    """
    await db.execute(text("DELETE FROM conversation_cache "
                          "WHERE site_key = :sk AND status = 'auto'"), {"sk": site_key})
    await db.execute(text("DELETE FROM answer_audio_cache WHERE site_key = :sk"),
                     {"sk": site_key})


async def purge_site(db: AsyncSession, site_key: str) -> dict[str, int]:
    """Remove a site's knowledge tree and all per-site state.

    Returns the number of rows removed per table. Does not commit — the caller
    owns the transaction so the purge and the website delete land together.
    """
    removed: dict[str, int] = {}
    res = await db.execute(
        text("DELETE FROM cortex_trees WHERE entity_id = :eid"),
        {"eid": site_entity_id(site_key)},
    )
    removed["cortex_trees"] = res.rowcount or 0
    for table in _SITE_TABLES:
        if await _table_exists(db, table):
            res = await db.execute(
                text(f"DELETE FROM {table} WHERE site_key = :sk"), {"sk": site_key}
            )
            removed[table] = res.rowcount or 0
    return removed
