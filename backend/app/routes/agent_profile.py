"""
Per-website agent profile — the "brain" a tenant configures (docs/defects.md D-9).

The agent's name, the company it represents and its brand voice; the visitor
personas it may switch between; the concrete example the guided tour ends on;
and the site's navigable routes (sitemap). Ingested URL sources add routes
automatically; this endpoint lets the owner review and edit all of it.

Edits apply to new turns at once on the replica that saved them, and on other
replicas within the profile cache TTL (app/orchestrator/profile.py).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.orchestrator.profile import SiteProfile, load_profile, save_profile
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["profile"])

_SLUG = r"^[a-z0-9][a-z0-9-]{0,39}$"


def _check_path(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith("/") or len(value) > 200:
        raise ValueError(f"must be a site path starting with '/': {value!r}")
    return value


class PersonaIn(BaseModel):
    slug: str = Field(..., pattern=_SLUG)
    label: str = Field(..., min_length=1, max_length=60)
    focus: str = Field("", max_length=200)
    tone: str = Field("", max_length=200)
    landing: str = Field("", max_length=200)

    @field_validator("landing")
    @classmethod
    def _landing_is_path(cls, v: str) -> str:
        return _check_path(v) if v else v


class ProfileUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    agent_name: Optional[str] = Field(None, min_length=1, max_length=40)
    company_name: Optional[str] = Field(None, min_length=1, max_length=80)
    brand_voice: Optional[str] = Field(None, min_length=1, max_length=300)
    personas: Optional[list[PersonaIn]] = Field(None, max_length=8)
    closing_use_case: Optional[str] = Field(None, max_length=800)
    routes: Optional[list[str]] = Field(None, max_length=500)
    dynamic_prefixes: Optional[list[str]] = Field(None, max_length=20)

    @field_validator("personas")
    @classmethod
    def _unique_slugs(cls, v: Optional[list[PersonaIn]]) -> Optional[list[PersonaIn]]:
        if v is not None and len({p.slug for p in v}) != len(v):
            raise ValueError("persona slugs must be unique")
        return v

    @field_validator("routes", "dynamic_prefixes")
    @classmethod
    def _paths(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return [_check_path(p) for p in v] if v is not None else v


@router.get("/profile")
async def get_profile(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return (await load_profile(db, site.site_key)).to_dict()


@router.put("/profile")
async def update_profile(
    body: ProfileUpdate,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    current = await load_profile(db, site.site_key)
    updated = SiteProfile.from_dict(body.model_dump(exclude_unset=True), current)
    await save_profile(db, updated)
    return updated.to_dict()
