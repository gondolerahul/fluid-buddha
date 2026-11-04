"""
The shared Redis client (F-3), when ``REDIS_URL`` is set.

Used for state that must be the same on every backend replica: chat sessions
(``app.transport.session_store``) and the public per-minute rate limit
(``app.transport.guard``). Without ``REDIS_URL`` both stay in process, which
is correct for a single replica.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def redis_client() -> Optional[Any]:
    from app.config import get_settings

    url = get_settings().redis_url.strip()
    if not url:
        return None
    import redis.asyncio as redis

    logger.info("shared state in Redis (%s)", url.split("@")[-1])  # no credentials in logs
    return redis.from_url(url, decode_responses=True, socket_timeout=2.0,
                          socket_connect_timeout=2.0, health_check_interval=30)
