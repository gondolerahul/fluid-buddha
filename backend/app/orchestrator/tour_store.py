"""
Persistence for the pre-planned website tour (Req 5).

A tiny key/value table keyed by site — kept deliberately separate from the
CORTEX ORM so it needs no migration and can't perturb the knowledge schema.
Written once at ingestion (``plan_tour``), read at runtime when a visitor opens
the agent.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.tour import TourPlan

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS site_tours (
    site_key   text PRIMARY KEY,
    plan       jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
)
"""


async def ensure_table(db: AsyncSession) -> None:
    await db.execute(text(_DDL))


async def save_plan(db: AsyncSession, plan: TourPlan) -> None:
    await ensure_table(db)
    await db.execute(
        text(
            "INSERT INTO site_tours (site_key, plan, updated_at) "
            "VALUES (:k, :p, now()) "
            "ON CONFLICT (site_key) DO UPDATE SET plan = :p, updated_at = now()"
        ),
        {"k": plan.site_key, "p": json.dumps(plan.to_dict())},
    )
    await db.commit()
    logger.info("saved tour plan for site=%s (%d stops)", plan.site_key, len(plan.stops))


async def load_plan(db: AsyncSession, site_key: str) -> Optional[TourPlan]:
    try:
        await ensure_table(db)
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
