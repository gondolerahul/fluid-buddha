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

    async def live_sweep() -> object:
        from app.live import store as live_store

        async with session_scope() as db:
            return await live_store.sweep(db) or None

    engines = None

    async def classify_turns() -> object:
        """Insights v2 (M2-5): label new visitor turns (rules in mock mode)."""
        nonlocal engines
        from app.insights.classify import run_job

        llm = None
        if not settings.mock_ai:
            if engines is None:
                from app.ai.factory import build_engines
                engines = build_engines(settings)
            llm = engines.llm
        return await run_job(session_scope, llm=llm, model=settings.fast_model) or None

    async def weekly_digest() -> object:
        from app.notify import digest

        async with session_scope() as db:
            return await digest.send_due(db) or None

    async def action_payments() -> object:
        """M2-8: unpaid payment links, checked with Razorpay (webhook fallback)."""
        from app.routes.actions import check_payments

        return await check_payments() or None

    async def access_review() -> object:
        """M2-11: each account's Owners and Admins get the quarter's access review."""
        from app.notify import access_review as review

        async with session_scope() as db:
            return await review.send_due(db) or None

    async def session_cleanup() -> object:
        """M2-11: sessions that ended more than 30 days ago (kept a while for review)."""
        from sqlalchemy import text

        async with session_scope() as db:
            res = await db.execute(text(
                "DELETE FROM user_sessions WHERE expires_at < now() - interval '30 days' "
                "OR revoked_at < now() - interval '30 days'"))
            await db.commit()
            return res.rowcount or None

    s = Scheduler()
    s.add(Job("retention_sweep", settings.retention_sweep_minutes * 60, retention))
    s.add(Job("email_outbox", settings.email_outbox_interval_seconds, outbox, run_at_start=True))
    s.add(Job("email_outbox_cleanup", 24 * 3600 if settings.email_outbox_interval_seconds else 0,
              outbox_cleanup))
    s.add(Job("audit_retention", 24 * 3600, audit_retention))
    s.add(Job("live_presence_sweep", 300, live_sweep))
    s.add(Job("insights_classify", settings.insights_classify_seconds, classify_turns))
    s.add(Job("weekly_digest", settings.digest_check_seconds, weekly_digest))
    s.add(Job("action_payments", settings.action_payments_seconds, action_payments))
    s.add(Job("access_review", settings.access_review_check_seconds, access_review))
    s.add(Job("session_cleanup", 24 * 3600, session_cleanup))
    return s
