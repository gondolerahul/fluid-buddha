"""
Persistence for the pre-planned website tour (Req 5).

A tiny key/value table keyed by site (``site_tours``, created by the
migrations), kept separate from the CORTEX ORM so it can't perturb the
knowledge schema.
Written at ingestion (``plan_tour``), read at runtime when a visitor opens
the agent. A plan the tenant saved by hand is flagged ``edited`` so a later
re-ingestion never silently overwrites it (D-10); only an explicit "regenerate"
replaces it.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.tour import TourPlan

logger = logging.getLogger(__name__)


async def save_plan(
    db: AsyncSession, plan: TourPlan, *, edited: bool = False, keep_edited: bool = False
) -> bool:
    """Upsert ``plan``. ``edited`` marks a hand-made plan; ``keep_edited`` (used by
    re-ingestion) leaves an existing hand-edited plan untouched. Returns whether
    the plan was written."""
    guard = " WHERE NOT site_tours.edited" if keep_edited else ""
    res = await db.execute(
        text(
            "INSERT INTO site_tours (site_key, plan, edited, updated_at) "
            "VALUES (:k, :p, :e, now()) "
            "ON CONFLICT (site_key) DO UPDATE SET plan = :p, edited = :e, "
            "updated_at = now()" + guard + " RETURNING site_key"
        ),
        {"k": plan.site_key, "p": json.dumps(plan.to_dict()), "e": edited},
    )
    written = res.first() is not None
    await db.commit()
    if written:
        logger.info("saved tour plan for site=%s (%d stops, edited=%s)",
                    plan.site_key, len(plan.stops), edited)
    else:
        logger.info("kept hand-edited tour for site=%s", plan.site_key)
    return written


async def is_edited(db: AsyncSession, site_key: str) -> bool:
    res = await db.execute(
        text("SELECT edited FROM site_tours WHERE site_key = :k"), {"k": site_key}
    )
    return bool(res.scalar())


async def load_plan(db: AsyncSession, site_key: str) -> Optional[TourPlan]:
    try:
        res = await db.execute(
            text("SELECT plan FROM site_tours WHERE site_key = :k"), {"k": site_key}
        )
        row = res.scalar()
    except Exception as exc:  # never let a missing tour break a conversation
        logger.warning("load_plan failed for %s: %s", site_key, exc)
        return None
    if not row:
        return None
    data = row if isinstance(row, dict) else json.loads(row)
    plan = TourPlan.from_dict(data)
    return plan if plan.is_usable() else None
