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
    res = await db.execute(
        text(f"SELECT {_COLS} FROM tenant_sources WHERE website_id = :wid "
             "ORDER BY created_at DESC"),
        {"wid": website_id},
    )
    return [_row(r) for r in res.mappings().all()]


async def get_source(
    db: AsyncSession, source_id: uuid.UUID, website_id: uuid.UUID
) -> Optional[Source]:
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


async def upsert_url_source(
    db: AsyncSession, *, website_id: uuid.UUID, url: str, name: str
) -> uuid.UUID:
    """Add a crawled page as a URL source, or queue an existing one for
    re-ingestion (a re-crawl refreshes pages instead of duplicating them)."""
    existing = (await db.execute(
        text("SELECT id FROM tenant_sources WHERE website_id = :wid AND kind = 'url' "
             "AND content = :url ORDER BY created_at LIMIT 1"),
        {"wid": website_id, "url": url},
    )).scalar()
    if existing:
        await db.execute(
            text("UPDATE tenant_sources SET status = 'pending', error = NULL, name = :n "
                 "WHERE id = :id"),
            {"id": existing, "n": name},
        )
        await db.commit()
        return existing
    s = await add_source(db, website_id=website_id, kind="url", name=name, content=url)
    return s.id


async def pending_sources(db: AsyncSession, website_id: uuid.UUID) -> list[Source]:
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


async def _read_url(url: str) -> tuple[str, bool]:
    """Fetch a URL source: ``(text, is_page)``. A PDF is read for its text but
    isn't a page the agent can navigate to."""
    from app.onboarding.documents import pdf_text
    from app.onboarding.html import parse_page
    from app.tenancy.url_fetch import ALLOWED_CONTENT_TYPES, fetch_public

    # SSRF-guarded fetch: public addresses only, every redirect re-checked,
    # size/type capped (docs/defects.md D-5).
    got = await fetch_public(url, allowed_types=ALLOWED_CONTENT_TYPES + ("application/pdf",),
                             max_bytes=10_000_000)
    if got.content_type == "application/pdf":
        return pdf_text(got.body), False
    if got.content_type == "text/plain":
        return got.text, True
    info = parse_page(got.text, got.url)
    body = info.text or strip_html(got.text)
    if info.title and not body.startswith(info.title):
        body = f"{info.title}\n\n{body}"
    return body, True


async def run_ingestion(
    site_key: str, website_id: uuid.UUID,
    prefetched: Optional[dict[str, tuple[str, bool]]] = None,
) -> dict:
    """Ingest a website's pending sources into its CORTEX tree, mark each source's
    outcome, and re-plan the guided tour. Self-contained (opens its own sessions)
    so it can run as a FastAPI ``BackgroundTask``. ``prefetched`` maps a URL
    source to ``(text, is_page)`` the crawler already read (WS9), so it isn't
    downloaded twice."""
    from app.db import SessionLocal
    from app.cortex.purge import delete_document_nodes, invalidate_site_caches
    from app.orchestrator.profile import merge_routes
    from app.orchestrator.sitemap import route_from_url
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
                if prefetched and s.content in prefetched:
                    body, is_page = prefetched[s.content]
                else:
                    body, is_page = await _read_url(s.content)
                if not (body or "").strip():
                    raise ValueError("no readable text at URL")
                # The URL's path is a real page on the site: it becomes a
                # navigable route and lets the tour visit it (D-9).
                doc = SourceDocument(filename=s.name or s.content,
                                     route=(route_from_url(s.content) or None) if is_page else None,
                                     content=body, document_id=s.id)
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
        # Add crawled pages to the site's sitemap so the agent can navigate there.
        routes = [d.route for d in good_docs if d.route]
        if routes:
            async with SessionLocal() as db:
                await merge_routes(db, site_key, routes)
        await plan_and_save_tour(site_key, good_docs)

    logger.info("website ingestion site=%s ingested=%d failed=%d nodes=%d",
                site_key, ingested, failed, total_nodes)
    return {"ingested": ingested, "failed": failed, "nodes": total_nodes}
