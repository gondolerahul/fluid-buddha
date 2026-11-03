"""
Shared pytest fixtures that keep the suite deterministic and order-independent.

Two cross-test leaks previously made the suite hang on every run after the
first (see ``docs/defects.md`` D-7):

1. Tests mutate the process-wide ``Settings`` singleton
   (``episodic_min_episodes = 1``) and never restore it, so a later test
   replays a cached answer it never set up for.
2. The conversation/audio caches accumulate rows in the shared database, so a
   later WebSocket test gets an unexpected replay and blocks forever waiting
   for audio segments a replay never sends.

The autouse fixtures below restore the settings and clear the caches around
every test, so each test is independent of order and of what ran before it.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

# Per-site replay state that must not leak between tests.
_CACHE_TABLES = ("conversation_cache", "answer_audio_cache")


@pytest.fixture(autouse=True)
def restore_settings():
    """Snapshot the shared ``Settings`` singleton and restore it after the test.

    ``get_settings()`` is ``lru_cache``d, so every test (and the runtime built
    at app startup) sees the same instance. Tests that tweak a knob such as
    ``episodic_min_episodes`` would otherwise leave it changed for the rest of
    the session.
    """
    settings = get_settings()
    snapshot = settings.model_dump()
    try:
        yield
    finally:
        for field, value in snapshot.items():
            setattr(settings, field, value)


async def _truncate_caches() -> None:
    # Use a throwaway engine with NullPool, created and disposed inside this
    # call's event loop. The app's shared async engine must not be touched from
    # here: driving it from the fixture's short-lived loop would bind its
    # asyncpg pool to a loop that then closes, breaking the test's own session.
    engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            for table in _CACHE_TABLES:
                # Tables are created lazily on first use; skip ones not there yet.
                exists = (
                    await conn.execute(text("SELECT to_regclass(:t)"), {"t": table})
                ).scalar()
                if exists:
                    await conn.execute(text(f"TRUNCATE {table}"))
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def clean_caches():
    """Clear the replay and audio caches before each test.

    Prevents a cached turn seeded by one test from triggering an unexpected
    replay in another, which is the direct cause of the D-7 WebSocket hang.
    """
    asyncio.run(_truncate_caches())
    yield
