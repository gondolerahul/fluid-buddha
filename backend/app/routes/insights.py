"""
Insights v1 (WS10): what visitors ask, what the agent couldn't answer, and the
transcripts behind it.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.insights import store as insights
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["insights"])


@router.get("/insights")
async def get_insights(
    days: int = Query(30, ge=1, le=365),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await insights.summary(db, site.site_key, days)


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    items, total = await insights.list_conversations(
        db, site.site_key, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    conv = await insights.get_conversation(db, site.site_key, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv
