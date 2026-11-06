"""
Tenant website management (req B): a logged-in tenant attaches and manages the
websites the ``<fluid-buddha>`` agent runs on. All routes are tenant-scoped via
``current_tenant`` — a tenant can only ever see/touch their own sites.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import current_tenant
from app.db import get_session
from app.tenancy import store

router = APIRouter(prefix="/tenant/websites", tags=["websites"])

_INTELLIGENCE = {"basic", "high", "advance", "extreme"}
_DESIGN = {"level1", "level2", "level3"}  # the SDK's three design levels


class WebsiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    domain: str | None = None
    intelligence: str = "advance"
    design: str = "level1"
    accent: str | None = None
    # Start from a vertical template (M2-9): saas, education, real_estate, healthcare.
    template: str | None = None


class WebsiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    domain: str | None = None
    intelligence: str | None = None
    design: str | None = None
    accent: str | None = None
    status: str | None = None


def _validate_levels(intelligence: str | None, design: str | None) -> None:
    if intelligence is not None and intelligence not in _INTELLIGENCE:
        raise HTTPException(422, f"intelligence must be one of {sorted(_INTELLIGENCE)}")
    if design is not None and design not in _DESIGN:
        raise HTTPException(422, f"design must be one of {sorted(_DESIGN)}")


async def _owned(db: AsyncSession, website_id: str, tenant) -> store.Website:
    try:
        wid = uuid.UUID(website_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Website not found")
    site = await store.get_website(db, wid, tenant.id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Website not found")
    return site


@router.get("")
async def list_websites(
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    return [w.public() for w in await store.list_websites(db, tenant.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_website(
    body: WebsiteCreate,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _validate_levels(body.intelligence, body.design)
    from app.licence.guard import check_limit
    await check_limit(db, "sites")   # self-hosted installs (M3-5)
    pack = None
    if body.template:
        from app import templates
        pack = templates.get(body.template)
        if pack is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No such template")
    site = await store.create_website(
        db, tenant_id=tenant.id, name=body.name, domain=body.domain,
        intelligence=body.intelligence, design=body.design, accent=body.accent,
    )
    if pack is not None:
        from app.templates.apply import apply
        await db.commit()   # the site exists before its profile is written
        await apply(db, site.site_key, pack)
        await db.commit()
    return site.public()


@router.get("/{website_id}")
async def get_website(
    website_id: str,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return (await _owned(db, website_id, tenant)).public()


@router.patch("/{website_id}")
async def update_website(
    website_id: str,
    body: WebsiteUpdate,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    site = await _owned(db, website_id, tenant)
    _validate_levels(body.intelligence, body.design)
    updated = await store.update_website(
        db, site.id, tenant.id, **body.model_dump(exclude_none=True)
    )
    return updated.public()


@router.post("/{website_id}/rotate-key")
async def rotate_key(
    website_id: str,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Issue a new widget key; the old one stops working immediately. Also gives
    sites created before widget keys existed their first key."""
    site = await _owned(db, website_id, tenant)
    return (await store.rotate_public_key(db, site.id, tenant.id)).public()


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_website(
    website_id: str,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> None:
    site = await _owned(db, website_id, tenant)
    await store.delete_website(db, site.id, tenant.id, site.site_key)
