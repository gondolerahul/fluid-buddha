"""
Abuse guard for the public widget paths (docs/defects.md D-3).

Two per-site limits, checked before each public turn:

- **Rate limit** — at most ``public_rate_limit_per_min`` turns per site per
  minute (fixed window). With ``REDIS_URL`` the window is shared by every
  backend replica (F-3); without it, it is counted per replica.
- **Daily spend cap** — once a site's recorded ``usage_events.total_cost`` for
  the current UTC day reaches ``public_daily_spend_cap_usd``, further turns are
  refused until the next day.

Either limit is disabled by setting it to 0. The same check raises the
site's cost alerts (80 % and 100 % of the cap, and its own threshold) —
see ``app/analytics/alerts.py``.

- **Plan limit** (WS12) — a site on the Free plan stops starting new
  conversations once its account's monthly allowance is used.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

RATE_LIMITED = "rate_limited"
SPEND_CAP_REACHED = "spend_cap_reached"
PLAN_LIMIT_REACHED = "plan_limit_reached"

# What the visitor is told (the reason codes are for logs and the client).
REFUSAL_MESSAGES = {
    RATE_LIMITED: "I'm getting a lot of questions right now. Please try again in a minute.",
    SPEND_CAP_REACHED: "I'm not available for the rest of today. Please try again tomorrow.",
    PLAN_LIMIT_REACHED: "I'm not available right now. Please contact the team directly.",
}


class RateLimiter:
    """Fixed-window counter per key. Thread-safe (the test client and the ASGI
    server may call it from different threads)."""

    def __init__(self, window_s: float = 60.0) -> None:
        self.window_s = window_s
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}  # key -> (window index, count)

    def allow(self, key: str, limit: int, now: Optional[float] = None) -> bool:
        if limit <= 0:
            return True
        window = int((time.time() if now is None else now) // self.window_s)
        with self._lock:
            start, count = self._windows.get(key, (window, 0))
            if start != window:
                start, count = window, 0
            if count >= limit:
                self._windows[key] = (start, count)
                return False
            self._windows[key] = (start, count + 1)
            return True


_limiter = RateLimiter()


async def _allow(site_key: str, limit: int) -> bool:
    """The rate check, in Redis when configured (one window for all
    replicas), else in process. A Redis outage falls back to in-process."""
    if limit <= 0:
        return True
    from app.shared_state import redis_client

    client = redis_client()
    if client is not None:
        window = int(time.time() // _limiter.window_s)
        key = f"fb:rl:{site_key}:{window}"
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, int(_limiter.window_s * 2))
            return count <= limit
        except Exception:
            pass
    return _limiter.allow(site_key, limit)


async def spent_today_usd(db: AsyncSession, site_key: str) -> float:
    """Recorded model/TTS spend for ``site_key`` in the current UTC day — the
    platform's part: model cost an account pays its own provider (M3-4) is
    left out, since it costs the platform nothing."""
    exists = (await db.execute(text("SELECT to_regclass('usage_events')"))).scalar()
    if not exists:
        return 0.0
    res = await db.execute(
        text(
            "SELECT COALESCE(SUM(total_cost - byo_llm_cost), 0) FROM usage_events "
            "WHERE site_key = :sk "
            "AND (created_at AT TIME ZONE 'UTC')::date = (now() AT TIME ZONE 'UTC')::date"
        ),
        {"sk": site_key},
    )
    return float(res.scalar() or 0.0)


async def check_public_budget(
    db: AsyncSession, site_key: str, settings: Settings,
    session_id: Optional[str] = None,
) -> Optional[str]:
    """Return a refusal reason if this public turn must be blocked, else None.

    Every turn that passes the rate check counts against the window, including
    one the spend cap then refuses.
    """
    if not await _allow(site_key, settings.public_rate_limit_per_min):
        return RATE_LIMITED
    from app.analytics import alerts

    cap = settings.public_daily_spend_cap_usd
    threshold = await alerts.site_threshold(db, site_key)
    if cap > 0 or threshold:
        spent = await spent_today_usd(db, site_key)
        alerts.schedule(site_key, spent, cap, threshold)   # background; once a day each
        if cap > 0 and spent >= cap:
            return SPEND_CAP_REACHED
    from app.billing.store import over_plan_limit

    if await over_plan_limit(db, site_key, session_id):
        return PLAN_LIMIT_REACHED
    return None
