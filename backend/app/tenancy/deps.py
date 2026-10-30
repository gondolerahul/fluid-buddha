"""
Shared FastAPI dependency: resolve the ``{website_id}`` path param to a Website
owned by the authenticated tenant (404 otherwise). Used by every per-website
sub-resource router (ingestion, tour, cache, analytics).
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import current_tenant
from app.db import get_session
from app.tenancy import store


async def owned_website(
    website_id: str,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> store.Website:
    try:
        wid = uuid.UUID(website_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Website not found")
    site = await store.get_website(db, wid, tenant.id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Website not found")
    return site
