"""
Privacy settings and erasure (WS8).

- ``GET/PUT /tenant/websites/{id}/privacy`` — PII masking, microphone consent,
  the privacy-policy link the widget shows, and how long transcripts and leads
  are kept.
- ``POST /tenant/websites/{id}/privacy/erase`` — delete one visitor's leads and
  the conversations they came from (a deletion request).
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.leads.store import EMAIL_RE
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.trust import retention
from app.trust.settings import (
    LEAD_RETENTION_DAYS, TRANSCRIPT_RETENTION_DAYS, Privacy, get_privacy, save_privacy,
)

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["privacy"])


class PrivacyUpdate(BaseModel):
    redact_pii: bool
    consent_required: bool
    privacy_policy_url: Optional[str] = Field(None, max_length=500)
    transcript_retention_days: int
    lead_retention_days: int

    @field_validator("privacy_policy_url")
    @classmethod
    def _policy_url(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        if not v:
            return None
        # The widget renders this as a link: only web URLs, never javascript: etc.
        u = urlparse(v)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ValueError("the privacy policy link must be an http(s) URL")
        return v

    @field_validator("transcript_retention_days")
    @classmethod
    def _transcripts(cls, v: int) -> int:
        if v not in TRANSCRIPT_RETENTION_DAYS:
            raise ValueError(f"must be one of {TRANSCRIPT_RETENTION_DAYS} (0 = keep)")
        return v

    @field_validator("lead_retention_days")
    @classmethod
    def _leads(cls, v: int) -> int:
        if v not in LEAD_RETENTION_DAYS:
            raise ValueError(f"must be one of {LEAD_RETENTION_DAYS} (0 = keep)")
        return v


class EraseRequest(BaseModel):
    email: str = Field(..., max_length=320)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("a valid email address is required")
        return v


@router.get("/privacy")
async def read_privacy(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return (await get_privacy(db, site.site_key)).to_dict()


@router.put("/privacy")
async def update_privacy(
    body: PrivacyUpdate,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    saved = await save_privacy(db, site.site_key, Privacy(**body.model_dump()))
    return saved.to_dict()


@router.post("/privacy/erase")
async def erase_visitor(
    body: EraseRequest,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await retention.erase_visitor(db, site.site_key, body.email)
