"""
Schema migrations (F-3): the database is at the latest revision and holds every
table the app uses, with no per-request DDL left in the code.
"""
from __future__ import annotations

import asyncio
import pathlib
import re

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

BACKEND = pathlib.Path(__file__).resolve().parents[1]
TABLES = {
    "cortex_trees", "cortex_nodes", "cortex_edges", "tenants", "tenant_websites",
    "tenant_sources", "site_profiles", "site_tours", "conversation_cache",
    "answer_audio_cache", "usage_events", "conversations", "conversation_turns",
}


def _query(sql: str) -> list:
    async def run() -> list:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return [r[0] for r in (await conn.execute(text(sql))).all()]
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_database_is_at_head_with_every_table():
    head = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_current_head()
    assert _query("SELECT version_num FROM alembic_version") == [head]
    present = set(_query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    assert TABLES <= present


def test_no_runtime_ddl_outside_migrations():
    ddl = re.compile(r"\b(CREATE TABLE|ALTER TABLE|CREATE (UNIQUE )?INDEX)\b", re.IGNORECASE)
    offenders = [str(p.relative_to(BACKEND)) for d in ("app", "ingestion")
                 for p in (BACKEND / d).rglob("*.py") if ddl.search(p.read_text("utf-8"))]
    assert offenders == [], f"schema changes belong in a migration: {offenders}"
