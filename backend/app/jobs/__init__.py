"""Background jobs (M2-0): the scheduler and the app's job list."""
from __future__ import annotations

from app.config import Settings
from app.jobs.scheduler import Job, Scheduler


def build_scheduler(settings: Settings) -> Scheduler:
    """Every periodic job the app runs. An interval of 0 turns a job off."""
    from app.db import session_scope
    from app.notify import email
    from app.trust.retention import purge_expired

    async def retention() -> object:
        async with session_scope() as db:
            removed = await purge_expired(db)
        return removed if any(removed.values()) else None

    async def outbox() -> object:
        async with session_scope() as db:
            counts = await email.deliver_due(db)
        return counts if any(counts.values()) else None

    async def outbox_cleanup() -> object:
        async with session_scope() as db:
            return await email.purge_old(db) or None

    async def audit_retention() -> object:
        from app import audit

        async with session_scope() as db:
            return await audit.purge_old(db) or None

    s = Scheduler()
    s.add(Job("retention_sweep", settings.retention_sweep_minutes * 60, retention))
    s.add(Job("email_outbox", settings.email_outbox_interval_seconds, outbox, run_at_start=True))
    s.add(Job("email_outbox_cleanup", 24 * 3600 if settings.email_outbox_interval_seconds else 0,
              outbox_cleanup))
    s.add(Job("audit_retention", 24 * 3600, audit_retention))
    return s
