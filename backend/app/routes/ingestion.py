"""
Ingestion control (req C): a tenant manages what each website's agent knows.

They can attach sources (pasted text, a URL, or an uploaded document), see the
ingestion status, and trigger a run that feeds pending sources into the site's
CORTEX knowledge tree. Uploaded files are decoded as UTF-8 text (markdown / txt /
html / csv / json); binary formats like PDF need extraction first (follow-up).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.tenancy import sources as src_store
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.url_fetch import UnsafeURLError, check_url

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["ingestion"])

_MAX_UPLOAD = 2 * 1024 * 1024  # 2 MB of text


class SourceCreate(BaseModel):
    kind: str = Field(..., pattern="^(text|url)$")
    name: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


async def _document_count(site_key: str) -> int:
    from ingestion.ingest import _document_count as count
    try:
        return await count(site_key)
    except Exception:
        return 0


@router.get("/ingestion")
async def get_ingestion(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    items = await src_store.list_sources(db, site.id)
    by_status = {s: 0 for s in src_store.STATUSES}
    for it in items:
        by_status[it.status] = by_status.get(it.status, 0) + 1
    return {
        "site_key": site.site_key,
        "document_count": await _document_count(site.site_key),
        "counts": by_status,
        "sources": [it.public() for it in items],
    }


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def add_source(
    body: SourceCreate,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if body.kind == "url":
        # Reject unfetchable URLs up front (scheme, credentials, literal
        # non-public IP). DNS is re-checked at fetch time (docs/defects.md D-5).
        try:
            check_url(body.content)
        except UnsafeURLError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    s = await src_store.add_source(
        db, website_id=site.id, kind=body.kind, name=body.name, content=body.content
    )
    return s.public()


@router.post("/sources/upload", status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "File too large (max 2 MB of text).")
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "File has no readable UTF-8 text.")
    s = await src_store.add_source(
        db, website_id=site.id, kind="file",
        name=file.filename or "upload.txt", content=text,
    )
    return s.public()


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> None:
    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if not await src_store.delete_source(db, sid, site.id, site.site_key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")


@router.post("/ingestion/run", status_code=status.HTTP_202_ACCEPTED)
async def run_ingestion(
    background: BackgroundTasks,
    wait: bool = False,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    pending = await src_store.pending_sources(db, site.id)
    if not pending:
        return {"status": "noop", "pending": 0}
    if wait:  # synchronous run (used by tests / small batches)
        result = await src_store.run_ingestion(site.site_key, site.id)
        return {"status": "done", **result}
    background.add_task(src_store.run_ingestion, site.site_key, site.id)
    return {"status": "started", "pending": len(pending)}
