"""
Async database engine + schema bootstrap.

The schema (CORTEX's ORM tables, pgvector, and every app table) is owned by the
Alembic migrations in ``migrations/``; ``init_db`` applies them at startup.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

engine = create_async_engine(
    _settings.cortex_db_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _upgrade(sync_conn) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.attributes["connection"] = sync_conn
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Bring the schema to the latest migration (migrations/, F-3). Idempotent
    and safe to run from several replicas at once (advisory-locked)."""
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade)
    logger.info("schema ready (migrations at head)")


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional session: commits on success, rolls back on error."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency variant of :func:`session_scope`."""
    async with session_scope() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
