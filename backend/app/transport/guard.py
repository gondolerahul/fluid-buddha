"""
Abuse guard for the public widget paths (docs/defects.md D-3).

Two per-site limits, checked before each public turn:

- **Rate limit** — at most ``public_rate_limit_per_min`` turns per site per
  minute (fixed window). In-process, so it is per backend replica; a shared
  store (Redis, plan F-3) is the follow-up for horizontal scaling.
- **Daily spend cap** — once a site's recorded ``usage_events.total_cost`` for
  the current UTC day reaches ``public_daily_spend_cap_usd``, further turns are
  refused until the next day.

Either limit is disabled by setting it to 0.
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


async def spent_today_usd(db: AsyncSession, site_key: str) -> float:
    """Recorded model/TTS spend for ``site_key`` in the current UTC day."""
    exists = (await db.execute(text("SELECT to_regclass('usage_events')"))).scalar()
    if not exists:
        return 0.0
    res = await db.execute(
        text(
            "SELECT COALESCE(SUM(total_cost), 0) FROM usage_events "
            "WHERE site_key = :sk "
            "AND (created_at AT TIME ZONE 'UTC')::date = (now() AT TIME ZONE 'UTC')::date"
        ),
        {"sk": site_key},
    )
    return float(res.scalar() or 0.0)


async def check_public_budget(
    db: AsyncSession, site_key: str, settings: Settings
) -> Optional[str]:
    """Return a refusal reason if this public turn must be blocked, else None.

    Every turn that passes the rate check counts against the window, including
    one the spend cap then refuses.
    """
    if not _limiter.allow(site_key, settings.public_rate_limit_per_min):
        return RATE_LIMITED
    cap = settings.public_daily_spend_cap_usd
    if cap > 0 and await spent_today_usd(db, site_key) >= cap:
        return SPEND_CAP_REACHED
    return None
