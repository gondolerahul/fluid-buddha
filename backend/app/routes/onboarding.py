"""
Self-serve onboarding API (WS9): crawl a website into its agent, and read back
the design tokens found on it.

    POST /tenant/websites/{id}/crawl   {url?, max_pages, max_depth}  → the job
    GET  /tenant/websites/{id}/crawl                                 → latest job
    GET  /tenant/websites/{id}/design                                → design tokens
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.design.system import DesignSystem
from app.onboarding import jobs
from app.onboarding.crawler import normalize
from app.onboarding.design import load_design
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.url_fetch import UnsafeURLError, check_url

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["onboarding"])


class CrawlRequest(BaseModel):
    # Defaults to the website's domain.
    url: Optional[str] = Field(None, max_length=2000)
    max_pages: int = Field(25, ge=1)
    max_depth: int = Field(2, ge=0)


def _start_url(body: CrawlRequest, site: store.Website) -> str:
    raw = (body.url or "").strip()
    if not raw:
        if not site.domain:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Enter your website's address to crawl.")
        raw = site.domain
    if "://" not in raw:
        raw = "https://" + raw
    try:
        check_url(raw)  # DNS is re-checked on every fetch
    except UnsafeURLError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return normalize(raw)


@router.post("/crawl", status_code=status.HTTP_202_ACCEPTED)
async def start_crawl(
    body: CrawlRequest,
    background: BackgroundTasks,
    wait: bool = False,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    settings = get_settings()
    url = _start_url(body, site)
    current = await jobs.latest_job(db, site.id)
    if current and current["status"] == "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "A crawl is already running for this website.")
    max_pages = min(body.max_pages, settings.crawl_max_pages)
    max_depth = min(body.max_depth, settings.crawl_max_depth)
    job = await jobs.create_job(db, site.id, url, max_pages, max_depth)
    jid = uuid.UUID(job["id"])
    args = (jid, site.id, site.site_key, url, max_pages, max_depth)
    if wait:  # synchronous run (tests / small sites)
        await jobs.run_crawl_job(*args)
        return await jobs.get_job(db, site.id, jid) or job
    background.add_task(jobs.run_crawl_job, *args)
    return job


@router.get("/crawl")
async def latest_crawl(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> Optional[dict]:
    return await jobs.latest_job(db, site.id)


@router.get("/design")
async def get_design(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """The tokens read off the site (``extracted``, or null before a crawl) and
    the full design system they produce (defaults fill the gaps)."""
    extracted = await load_design(db, site.site_key)
    return {
        "extracted": extracted,
        "design": DesignSystem.from_dict(extracted).to_dict(),
    }
