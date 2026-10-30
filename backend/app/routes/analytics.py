"""
Cost + performance analytics (req F, G).

One endpoint returns, for a website over an optional date range, the cost
breakdown by ASR / TTS / Fast LLM / Thinker LLM / Tool — grouped day-wise,
hour-wise, or session-wise — plus totals, latency percentiles, and the
generated-vs-cached split.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import usage
from app.db import get_session
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["analytics"])

_GROUPS = {"day", "hour", "session"}


def _parse_dt(value: str | None, label: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"{label} must be ISO-8601 (e.g. 2026-06-01T00:00:00Z)")


@router.get("/analytics")
async def get_analytics(
    group_by: str = Query("day"),
    frm: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if group_by not in _GROUPS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"group_by must be one of {sorted(_GROUPS)}")
    return await usage.analytics(
        db, site_key=site.site_key, group_by=group_by,
        frm=_parse_dt(frm, "from"), to=_parse_dt(to, "to"),
    )
