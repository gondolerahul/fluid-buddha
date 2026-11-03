"""Save leads the agent captured mid-conversation (``capture_lead``) and send
them on. Called by the transports after the turn is in the transcript, so the
lead links to its conversation and its summary includes this turn."""
from __future__ import annotations

import logging
from typing import Optional

from app.db import session_scope
from app.leads.delivery import deliver_lead
from app.leads.store import LeadIn, create_lead

logger = logging.getLogger(__name__)


async def save_captured(site_key: str, session_id: str, persona: Optional[str],
                        captured: list[LeadIn]) -> None:
    for lead in captured:
        try:
            async with session_scope() as db:
                saved = await create_lead(db, site_key=site_key, lead=lead,
                                          session_id=session_id, source="conversation",
                                          persona=persona)
        except Exception as exc:   # best-effort: never break the turn
            logger.warning("captured lead not saved for site=%s: %s", site_key, exc)
            continue
        await deliver_lead(saved)
