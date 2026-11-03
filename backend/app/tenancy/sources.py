"""
Per-website ingestion sources (req C).

A tenant controls what the agent knows about each site by attaching *sources*:
pasted text, a URL to crawl, or an uploaded document. Rows live in
``tenant_sources`` (raw DDL, same approach as the rest of the admin model) and
are fed into the existing CORTEX ingest path (``CortexBridge.ingest`` via
``ingestion.ingest.ingest_documents``) when the tenant clicks "run".
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

KINDS = ("text", "url", "file")
STATUSES = ("pending", "ingested", "failed")

_DDL = """
CREATE TABLE IF NOT EXISTS tenant_sources (
    id          uuid PRIMARY KEY,
    website_id  uuid NOT NULL REFERENCES tenant_websites(id) ON DELETE CASCADE,
    kind        text NOT NULL,
    name        text NOT NULL,
    content     text NOT NULL DEFAULT '',
    status      text NOT NULL DEFAULT 'pending',
    error       text,
    nodes       integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    ingested_at timestamptz
)
"""


@dataclass
class Source:
    id: uuid.UUID
    website_id: uuid.UUID
    kind: str
    name: str
    content: str
    status: str
    error: Optional[str]
    nodes: int
    created_at: datetime
    ingested_at: Optional[datetime]

    def public(self, *, include_content: bool = False) -> dict:
        d = {
            "id": str(self.id),
            "website_id": str(self.website_id),
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "error": self.error,
            "nodes": self.nodes,
            "preview": (self.content or "")[:240],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
        }
        if include_content:
            d["content"] = self.content
        return d


async def ensure_table(db: AsyncSession) -> None:
    await db.execute(text(_DDL))


_COLS = "id, website_id, kind, name, content, status, error, nodes, created_at, ingested_at"


def _row(r) -> Source:
    return Source(
        id=r["id"], website_id=r["website_id"], kind=r["kind"], name=r["name"],
        content=r["content"], status=r["status"], error=r["error"], nodes=r["nodes"],
        created_at=r["created_at"], ingested_at=r["ingested_at"],
    )


async def add_source(
    db: AsyncSession, *, website_id: uuid.UUID, kind: str, name: str, content: str
) -> Source:
    await ensure_table(db)
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    sid = uuid.uuid4()
    await db.execute(
        text("INSERT INTO tenant_sources (id, website_id, kind, name, content) "
             "VALUES (:id, :wid, :kind, :name, :content)"),
        {"id": sid, "wid": website_id, "kind": kind, "name": name, "content": content},
    )
    await db.commit()
    return (await get_source(db, sid, website_id))  # type: ignore[return-value]


async def list_sources(db: AsyncSession, website_id: uuid.UUID) -> list[Source]:
    await ensure_table(db)
    res = await db.execute(
        text(f"SELECT {_COLS} FROM tenant_sources WHERE website_id = :wid "
             "ORDER BY created_at DESC"),
        {"wid": website_id},
    )
    return [_row(r) for r in res.mappings().all()]


async def get_source(
    db: AsyncSession, source_id: uuid.UUID, website_id: uuid.UUID
) -> Optional[Source]:
    await ensure_table(db)
    res = await db.execute(
        text(f"SELECT {_COLS} FROM tenant_sources WHERE id = :id AND website_id = :wid"),
        {"id": source_id, "wid": website_id},
    )
    row = res.mappings().first()
    return _row(row) if row else None


async def delete_source(
    db: AsyncSession, source_id: uuid.UUID, website_id: uuid.UUID, site_key: str
) -> bool:
    """Delete a source AND the knowledge built from it (docs/defects.md D-6)."""
    from app.cortex.purge import delete_document_nodes, invalidate_site_caches

    await ensure_table(db)
    res = await db.execute(
        text("DELETE FROM tenant_sources WHERE id = :id AND website_id = :wid"),
        {"id": source_id, "wid": website_id},
    )
    if not (res.rowcount or 0):
        await db.rollback()
        return False
    await delete_document_nodes(db, site_key, source_id)
    await invalidate_site_caches(db, site_key)
    await db.commit()
    return True


async def pending_sources(db: AsyncSession, website_id: uuid.UUID) -> list[Source]:
    await ensure_table(db)
    res = await db.execute(
        text(f"SELECT {_COLS} FROM tenant_sources "
             "WHERE website_id = :wid AND status = 'pending' ORDER BY created_at"),
        {"wid": website_id},
    )
    return [_row(r) for r in res.mappings().all()]


async def mark_status(
    db: AsyncSession, source_id: uuid.UUID, status: str,
    *, nodes: int = 0, error: Optional[str] = None,
) -> None:
    await ensure_table(db)
    ingested = "now()" if status == "ingested" else "ingested_at"
    await db.execute(
        text(f"UPDATE tenant_sources SET status = :s, nodes = :n, error = :e, "
             f"ingested_at = {ingested} WHERE id = :id"),
        {"s": status, "n": nodes, "e": error, "id": source_id},
    )
    await db.commit()


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    """Crude HTML→text for crawled URLs (drop script/style, tags, collapse ws)."""
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text_only = _TAG_RE.sub(" ", html)
    text_only = re.sub(r"[ \t]+", " ", text_only)
    return _WS_RE.sub("\n\n", text_only).strip()


async def run_ingestion(site_key: str, website_id: uuid.UUID) -> dict:
    """Ingest a website's pending sources into its CORTEX tree, mark each source's
    outcome, and re-plan the guided tour. Self-contained (opens its own sessions)
    so it can run as a FastAPI ``BackgroundTask``."""
    from app.db import SessionLocal
    from app.cortex.purge import delete_document_nodes, invalidate_site_caches
    from app.tenancy.url_fetch import fetch_public_text
    from ingestion.ingest import ingest_documents, plan_and_save_tour
    from ingestion.scraper import SourceDocument

    async with SessionLocal() as db:
        pending = await pending_sources(db, website_id)
    if not pending:
        return {"ingested": 0, "failed": 0, "nodes": 0}

    ingested = failed = total_nodes = 0
    good_docs: list[SourceDocument] = []

    for s in pending:
        try:
            if s.kind == "url":
                # SSRF-guarded fetch: public addresses only, every redirect
                # re-checked, size/type capped (docs/defects.md D-5).
                body = strip_html(await fetch_public_text(s.content))
                if not body:
                    raise ValueError("no readable text at URL")
                doc = SourceDocument(filename=s.name or s.content, route=None, content=body,
                                     document_id=s.id)
            else:  # text | file — content is already plain text
                if not (s.content or "").strip():
                    raise ValueError("source has no content")
                doc = SourceDocument(filename=s.name, route=None, content=s.content,
                                     document_id=s.id)

            # Re-ingesting a source replaces its knowledge instead of
            # duplicating it (docs/defects.md D-10).
            async with SessionLocal() as db:
                await delete_document_nodes(db, site_key, s.id)
                await db.commit()
            n = await ingest_documents(site_key, [doc])
            total_nodes += n
            ingested += 1
            good_docs.append(doc)
            async with SessionLocal() as db:
                await mark_status(db, s.id, "ingested", nodes=n)
        except Exception as exc:  # one bad source must not fail the batch
            failed += 1
            logger.warning("ingest source %s failed: %s", s.id, exc)
            async with SessionLocal() as db:
                await mark_status(db, s.id, "failed", error=str(exc)[:500])

    if good_docs:
        # New knowledge makes cached answers stale.
        async with SessionLocal() as db:
            await invalidate_site_caches(db, site_key)
            await db.commit()
        await plan_and_save_tour(site_key, good_docs)

    logger.info("website ingestion site=%s ingested=%d failed=%d nodes=%d",
                site_key, ingested, failed, total_nodes)
    return {"ingested": ingested, "failed": failed, "nodes": total_nodes}
