"""
Conversation-cache view/edit (req E) — the tenant curates the answers/actions the
agent replays. Backed by ``EpisodicCache`` over the ``conversation_cache`` table.

Editing an entry writes straight back to the cache, so the next matching visitor
question replays the tenant's curated response. ``hit_count`` (how often an entry
was served) is surfaced for the generated-vs-cached view (req G); the full
generated-vs-cached split lives in the analytics endpoint (Phase 6).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Literal, Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["cache"])


class CacheEntryUpdate(BaseModel):
    question: str | None = None
    answer_text: str | None = None
    components: list[dict] | None = None
    actions: list[dict] | None = None
    # Golden answers (WS8): pin the approved answer, or block it from replay.
    status: Literal["auto", "pinned", "blocked"] | None = None


def _episodic(request: Request, db: AsyncSession, site_key: str):
    return request.app.state.runtime.episodic(db, site_key)


@router.get("/cache")
async def list_cache(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    kind: str = "turn",
    status_filter: Optional[Literal["auto", "pinned", "blocked"]] = None,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cache = _episodic(request, db, site.site_key)
    items, total = await cache.list_entries(
        kind=kind, limit=min(limit, 200), offset=offset, search=search,
        status=status_filter,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def _parse_id(entry_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cache entry not found")


@router.get("/cache/{entry_id}")
async def get_cache_entry(
    request: Request,
    entry_id: str,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    entry = await _episodic(request, db, site.site_key).get_entry(_parse_id(entry_id))
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cache entry not found")
    return entry


@router.put("/cache/{entry_id}")
async def update_cache_entry(
    request: Request,
    entry_id: str,
    body: CacheEntryUpdate,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cache = _episodic(request, db, site.site_key)
    eid = _parse_id(entry_id)
    if await cache.get_entry(eid) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cache entry not found")
    updated = await cache.update_entry(
        eid, question=body.question, answer_text=body.answer_text,
        components=body.components, actions=body.actions, status=body.status,
    )
    return updated


@router.delete("/cache/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cache_entry(
    request: Request,
    entry_id: str,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> None:
    if not await _episodic(request, db, site.site_key).delete_entry(_parse_id(entry_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cache entry not found")
