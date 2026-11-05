"""
Retention and erasure (WS8).

``purge_expired`` deletes visitor data older than each site's retention window:
conversations (their turns cascade) and auto-cached answers by
``transcript_retention_days``, leads by ``lead_retention_days``. Pinned and
blocked cache rows are the tenant's own curation, so they stay. A window of 0
keeps data. The app runs it on a timer (``retention_sweep_loop``).

``erase_visitor`` answers a deletion request: every lead with that email and the
conversations they came from.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_scope
from app.recaps import store as recap_store
from app.trust.settings import DEFAULT_TRANSCRIPT_DAYS

logger = logging.getLogger(__name__)

# Each site's window: its own setting, else the default (no row yet).
_WINDOW = (
    "SELECT d.site_key, COALESCE(p.{col}, :default) AS days "
    "FROM (SELECT DISTINCT site_key FROM {table}) d "
    "LEFT JOIN site_privacy p USING (site_key)"
)


async def _purge(db: AsyncSession, table: str, time_col: str, col: str,
                 default: int, extra: str = "") -> int:
    window = _WINDOW.format(col=col, table=table)
    res = await db.execute(text(
        f"WITH w AS ({window}) DELETE FROM {table} t USING w "
        f"WHERE t.site_key = w.site_key AND w.days > 0 "
        f"AND t.{time_col} < now() - w.days * interval '1 day' {extra}"
    ), {"default": default})
    return res.rowcount or 0


async def purge_expired(db: AsyncSession) -> dict[str, int]:
    removed = {
        "conversations": await _purge(db, "conversations", "last_at",
                                      "transcript_retention_days", DEFAULT_TRANSCRIPT_DAYS),
        "conversation_cache": await _purge(db, "conversation_cache", "created_at",
                                           "transcript_retention_days",
                                           DEFAULT_TRANSCRIPT_DAYS,
                                           "AND t.kind = 'turn' AND t.status = 'auto'"),
        "leads": await _purge(db, "leads", "created_at", "lead_retention_days", 0),
        # What people said during a takeover (M2-2) is part of the transcript.
        "live_messages": await _purge(db, "live_messages", "at",
                                      "transcript_retention_days", DEFAULT_TRANSCRIPT_DAYS),
        # Shared recap links past their expiry (M2-6); a recap also goes with
        # its conversation (ON DELETE CASCADE), so erasure removes it too.
        "recaps": await recap_store.purge_expired(db),
        # Action runs (M2-8) hold the visitor's details, like the transcript.
        "action_runs": await _purge(db, "action_runs", "created_at",
                                    "transcript_retention_days", DEFAULT_TRANSCRIPT_DAYS),
    }
    await db.commit()
    return removed


async def erase_visitor(db: AsyncSession, site_key: str, email: str) -> dict[str, int]:
    email = (email or "").strip().lower()
    # Actions they asked for (M2-8): by the email they gave, or in a
    # conversation that goes below.
    runs = (await db.execute(text(
        "DELETE FROM action_runs r WHERE r.site_key = :s AND (lower(r.inputs->>'email') = :e "
        "OR r.session_id IN (SELECT c.session_id FROM conversations c JOIN leads l "
        "ON l.conversation_id = c.id WHERE l.site_key = :s AND lower(l.email) = :e))"
    ), {"s": site_key, "e": email})).rowcount or 0
    await db.execute(text(
        "DELETE FROM live_messages m USING conversations c, leads l "
        "WHERE l.site_key = :s AND lower(l.email) = :e AND c.id = l.conversation_id "
        "AND m.site_key = c.site_key AND m.session_id = c.session_id"
    ), {"s": site_key, "e": email})
    convs = (await db.execute(text(
        "DELETE FROM conversations WHERE site_key=:s AND id IN "
        "(SELECT conversation_id FROM leads WHERE site_key=:s AND lower(email)=:e "
        " AND conversation_id IS NOT NULL)"
    ), {"s": site_key, "e": email})).rowcount or 0
    leads = (await db.execute(text(
        "DELETE FROM leads WHERE site_key=:s AND lower(email)=:e"
    ), {"s": site_key, "e": email})).rowcount or 0
    await db.commit()
    return {"leads": leads, "conversations": convs, "action_runs": runs}


async def retention_sweep_loop(interval_s: float) -> None:
    """Run ``purge_expired`` every ``interval_s`` seconds (first run after one
    interval, so startup stays fast). Errors are logged and the loop carries on."""
    while True:
        await asyncio.sleep(interval_s)
        try:
            async with session_scope() as db:
                removed = await purge_expired(db)
            if any(removed.values()):
                logger.info("retention sweep removed %s", removed)
        except Exception as exc:
            logger.warning("retention sweep failed: %s", exc)
