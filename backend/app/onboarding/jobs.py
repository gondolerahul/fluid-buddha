"""
The "crawl my website" job (WS9): paste a URL and the site's agent is ready.

    crawl → add each page as a URL source → ingest (reusing the fetched text)
          → personas (if the site has none) → design tokens → done

Progress is written to ``crawl_jobs`` as it goes, so the console can show the
phase, the page counts and how long it took end to end. Self-contained (opens
its own sessions) so it can run as a FastAPI ``BackgroundTask``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PHASES = ("crawling", "ingesting", "personas", "design", "done")
# A job still "running" after this long died with its server (restart/deploy).
_STALE_AFTER = timedelta(minutes=30)

_COLS = ("id, website_id, start_url, max_pages, max_depth, status, phase, pages_found, "
         "pages_ingested, pages_skipped, personas_added, design_found, error, "
         "started_at, finished_at")


def _public(row: Any) -> dict:
    d = dict(row)
    status = d["status"]
    error = d["error"]
    started = d["started_at"]
    if status == "running" and started and datetime.now(timezone.utc) - started > _STALE_AFTER:
        status, error = "failed", "The crawl was interrupted. Start it again."
    finished = d["finished_at"]
    return {
        "id": str(d["id"]),
        "website_id": str(d["website_id"]),
        "start_url": d["start_url"],
        "max_pages": d["max_pages"],
        "max_depth": d["max_depth"],
        "status": status,
        "phase": d["phase"],
        "pages_found": d["pages_found"],
        "pages_ingested": d["pages_ingested"],
        "pages_skipped": d["pages_skipped"],
        "personas_added": d["personas_added"],
        "design_found": d["design_found"],
        "error": error,
        "started_at": started.isoformat() if started else None,
        "finished_at": finished.isoformat() if finished else None,
        "duration_s": round((finished - started).total_seconds(), 1)
        if finished and started else None,
    }


async def create_job(db: AsyncSession, website_id: uuid.UUID, start_url: str,
                     max_pages: int, max_depth: int) -> dict:
    jid = uuid.uuid4()
    await db.execute(
        text("INSERT INTO crawl_jobs (id, website_id, start_url, max_pages, max_depth) "
             "VALUES (:id, :wid, :u, :mp, :md)"),
        {"id": jid, "wid": website_id, "u": start_url, "mp": max_pages, "md": max_depth},
    )
    await db.commit()
    return await get_job(db, website_id, jid)  # type: ignore[return-value]


async def get_job(db: AsyncSession, website_id: uuid.UUID, job_id: uuid.UUID) -> Optional[dict]:
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM crawl_jobs WHERE id = :id AND website_id = :wid"),
        {"id": job_id, "wid": website_id},
    )).mappings().first()
    return _public(row) if row else None


async def latest_job(db: AsyncSession, website_id: uuid.UUID) -> Optional[dict]:
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM crawl_jobs WHERE website_id = :wid "
             "ORDER BY started_at DESC LIMIT 1"),
        {"wid": website_id},
    )).mappings().first()
    return _public(row) if row else None


async def _update(job_id: uuid.UUID, **fields: Any) -> None:
    from app.db import SessionLocal

    sets = ", ".join(f"{k} = :{k}" for k in fields)
    if fields.get("status") in ("done", "failed"):
        sets += ", finished_at = now()"
    async with SessionLocal() as db:
        await db.execute(text(f"UPDATE crawl_jobs SET {sets} WHERE id = :id"),
                         {"id": job_id, **fields})
        await db.commit()


async def run_crawl_job(job_id: uuid.UUID, website_id: uuid.UUID, site_key: str,
                        start_url: str, max_pages: int, max_depth: int,
                        *, fetch=None) -> None:
    from app.config import get_settings
    from app.observability.metrics import CRAWL_JOBS
    from app.onboarding.crawler import crawl
    from app.tenancy.url_fetch import fetch_public

    settings = get_settings()
    fetch = fetch or fetch_public

    async def progress(n: int) -> None:
        await _update(job_id, pages_found=n)

    try:
        result = await crawl(start_url, max_pages=max_pages, max_depth=max_depth,
                             concurrency=settings.crawl_concurrency, fetch=fetch,
                             on_progress=progress)
        pages = [p for p in result.pages if p.ingestible]
        skipped = result.skipped + (len(result.pages) - len(pages))
        await _update(job_id, pages_found=len(result.pages), pages_skipped=skipped,
                      phase="ingesting")
        if not pages:
            why = ("robots.txt asks crawlers to stay out of this site"
                   if result.blocked_by_robots and not result.pages
                   else "No readable pages were found at that address")
            await _update(job_id, status="failed", error=why)
            CRAWL_JOBS.labels("failed").inc()
            return

        ingested = await _ingest(site_key, website_id, pages)
        await _update(job_id, pages_ingested=ingested, phase="personas")

        added = await _personas(site_key, result.pages, settings)
        await _update(job_id, personas_added=added, phase="design")

        found = await _design(site_key, result, fetch)
        await _update(job_id, design_found=found, phase="done", status="done")
        CRAWL_JOBS.labels("done").inc()
        logger.info("crawl job %s: site=%s pages=%d ingested=%d personas=%d design=%s",
                    job_id, site_key, len(result.pages), ingested, added, found)
    except Exception as exc:
        logger.exception("crawl job %s failed: %s", job_id, exc)
        await _update(job_id, status="failed", error=str(exc)[:500] or "Crawl failed")
        CRAWL_JOBS.labels("failed").inc()


async def _ingest(site_key: str, website_id: uuid.UUID, pages) -> int:
    from app.db import SessionLocal
    from app.tenancy.sources import run_ingestion, upsert_url_source

    ids: set[uuid.UUID] = set()
    async with SessionLocal() as db:
        for p in pages:
            ids.add(await upsert_url_source(db, website_id=website_id, url=p.url,
                                            name=p.title[:200]))
    prefetched = {p.url: (p.text, p.kind == "html") for p in pages}
    await run_ingestion(site_key, website_id, prefetched=prefetched)
    async with SessionLocal() as db:
        res = await db.execute(
            text("SELECT count(*) FROM tenant_sources WHERE id = ANY(:ids) "
                 "AND status = 'ingested'"),
            {"ids": list(ids)},
        )
        return int(res.scalar() or 0)


async def _personas(site_key: str, pages, settings) -> int:
    """Add derived personas to a site that has none (never overwrites)."""
    from app.db import SessionLocal
    from app.onboarding.personas import derive_personas
    from app.orchestrator.profile import load_profile, save_profile

    async with SessionLocal() as db:
        profile = await load_profile(db, site_key)
        if profile.personas:
            return 0
        llm = None
        if not settings.mock_ai:
            from app.ai.factory import build_engines
            from app.ai.providers import current_site
            current_site.set(site_key)   # the account's own model, if any (M3-4)
            llm = build_engines(settings).llm
        personas = await derive_personas(pages, llm, mock=settings.mock_ai)
        if not personas:
            return 0
        profile.personas = personas
        await save_profile(db, profile)
        return len(personas)


async def _design(site_key: str, result, fetch) -> bool:
    """Read the brand tokens off the homepage and its same-site stylesheets."""
    from app.db import SessionLocal
    from app.design.system import remember_extracted
    from app.onboarding.design import extract_design, same_site_stylesheets, save_design

    home = result.home
    if not home or not home.info:
        return False
    css: list[str] = []
    for href in same_site_stylesheets(home.info):
        try:
            got = await fetch(href, allowed_types=("text/css", "text/plain"),
                              max_bytes=1_000_000)
            css.append(got.text)
        except Exception as exc:  # a missing stylesheet just means fewer tokens
            logger.info("stylesheet skipped %s: %s", href, exc)
    design = extract_design(home.info, css)
    if not design:
        return False
    async with SessionLocal() as db:
        await save_design(db, site_key, design, home.url)
    remember_extracted(site_key, design)
    return bool(design.get("colors"))
