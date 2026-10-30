"""
Async database engine + schema bootstrap for the CORTEX memory engine.

CORTEX owns its SQLAlchemy ``Base`` (``cortex_memory.db.Base``). Importing
``cortex_memory.models`` registers the ORM classes onto that metadata, which is
all ``create_all`` needs. The ``vector`` extension must exist before the tables
(the node embedding column is ``vector(768)``).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Importing models registers CortexTree/CortexNode/CortexEdge on Base.metadata.
import cortex_memory.models  # noqa: F401
from cortex_memory.db import Base

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


async def init_db() -> None:
    """Create the pgvector extension and all CORTEX tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("CORTEX schema ready (pgvector + tables ensured)")


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
