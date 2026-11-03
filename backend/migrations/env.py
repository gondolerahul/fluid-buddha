"""
Alembic environment (F-3). Two entry points:

- the app: ``app.db.init_db`` runs ``upgrade head`` on its own async connection
  and hands the sync connection in via ``config.attributes["connection"]``;
- the CLI: ``alembic upgrade head`` opens an async engine from app settings.

Either way the upgrade holds a Postgres advisory lock, so several replicas
booting at once apply each migration exactly once.
"""
from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

# Any constant: only migrations take this lock.
_LOCK_ID = 7_314_202_611


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LOCK_ID})
    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_ID})


async def _run_cli() -> None:
    engine = create_async_engine(get_settings().cortex_db_url)
    try:
        async with engine.connect() as conn:
            await conn.run_sync(_run)
            await conn.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) mode is not supported; run against a database.")

shared = context.config.attributes.get("connection")
if shared is not None:
    _run(shared)
else:
    asyncio.run(_run_cli())
