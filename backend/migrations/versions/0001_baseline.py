"""Baseline: CORTEX tables + every app table that used to be created per request.

Written with IF NOT EXISTS throughout so a database created by the old
``ensure_table`` code adopts this revision cleanly; a fresh database gets the
same schema. New schema changes go in new revisions, never here.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-03
"""
from __future__ import annotations

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# Fixed by the cortex schema (Settings.embed_dim); the replay cache's embedding
# column must match the node embeddings it is compared with.
_EMBED_DIM = 768

_STATEMENTS = [
    # ---- tenancy ----
    """
    CREATE TABLE IF NOT EXISTS tenants (
        id            uuid PRIMARY KEY,
        email         text UNIQUE NOT NULL,
        password_hash text NOT NULL,
        name          text,
        created_at    timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tenant_websites (
        id           uuid PRIMARY KEY,
        tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        site_key     text UNIQUE NOT NULL,
        public_key   text,
        name         text NOT NULL,
        domain       text,
        intelligence text NOT NULL DEFAULT 'advance',
        design       text NOT NULL DEFAULT 'level1',
        accent       text,
        status       text NOT NULL DEFAULT 'active',
        created_at   timestamptz NOT NULL DEFAULT now()
    )
    """,
    # Pre-key databases (created before the widget key existed).
    "ALTER TABLE tenant_websites ADD COLUMN IF NOT EXISTS public_key text",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_websites_public_key "
    "ON tenant_websites(public_key)",
    """
    CREATE TABLE IF NOT EXISTS tenant_sources (
        id          uuid PRIMARY KEY,
        website_id  uuid NOT NULL REFERENCES tenant_websites(id) ON DELETE CASCADE,
        kind        text NOT NULL,
        name        text NOT NULL,
        content     text NOT NULL DEFAULT '',
        status      text NOT NULL DEFAULT 'pending',
        error       text,
        nodes       integer NOT NULL DEFAULT 0,
        created_at  timestamptz NOT NULL DEFAULT now(),
        ingested_at timestamptz
    )
    """,
    # ---- per-site brain ----
    """
    CREATE TABLE IF NOT EXISTS site_profiles (
        site_key   text PRIMARY KEY,
        profile    jsonb NOT NULL,
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS site_tours (
        site_key   text PRIMARY KEY,
        plan       jsonb NOT NULL,
        edited     boolean NOT NULL DEFAULT false,
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE site_tours ADD COLUMN IF NOT EXISTS edited boolean NOT NULL DEFAULT false",
    # ---- caches ----
    f"""
    CREATE TABLE IF NOT EXISTS conversation_cache (
        id          uuid PRIMARY KEY,
        site_key    text NOT NULL,
        persona     text,
        page        text,
        kind        text NOT NULL DEFAULT 'turn',
        q_norm      text NOT NULL,
        question    text NOT NULL,
        answer_text text NOT NULL,
        components  jsonb NOT NULL DEFAULT '[]'::jsonb,
        actions     jsonb NOT NULL DEFAULT '[]'::jsonb,
        channel     text,
        embedding   vector({_EMBED_DIM}),
        hit_count   integer NOT NULL DEFAULT 0,
        created_at  timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS conversation_cache_lookup "
    "ON conversation_cache (site_key, kind, q_norm)",
    """
    CREATE TABLE IF NOT EXISTS answer_audio_cache (
        text_hash   text PRIMARY KEY,
        site_key    text NOT NULL,
        sample_rate integer NOT NULL,
        pcm         bytea NOT NULL,
        created_at  timestamptz NOT NULL DEFAULT now()
    )
    """,
    # ---- analytics ----
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        id                uuid PRIMARY KEY,
        site_key          text NOT NULL,
        session_id        text,
        channel           text NOT NULL DEFAULT 'text',
        intent            text,
        persona           text,
        page              text,
        served_from_cache boolean NOT NULL DEFAULT false,
        asr_ms            double precision NOT NULL DEFAULT 0,
        tts_chars         integer NOT NULL DEFAULT 0,
        fast_in_tok       integer NOT NULL DEFAULT 0,
        fast_out_tok      integer NOT NULL DEFAULT 0,
        thinker_in_tok    integer NOT NULL DEFAULT 0,
        thinker_out_tok   integer NOT NULL DEFAULT 0,
        tool_calls        integer NOT NULL DEFAULT 0,
        asr_cost          double precision NOT NULL DEFAULT 0,
        tts_cost          double precision NOT NULL DEFAULT 0,
        fast_cost         double precision NOT NULL DEFAULT 0,
        thinker_cost      double precision NOT NULL DEFAULT 0,
        tool_cost         double precision NOT NULL DEFAULT 0,
        total_cost        double precision NOT NULL DEFAULT 0,
        latency_ms        double precision NOT NULL DEFAULT 0,
        created_at        timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS usage_events_site_time ON usage_events (site_key, created_at)",
]


def upgrade() -> None:
    # The CORTEX engine owns its ORM tables; create them from its metadata
    # (checkfirst, so existing tables are left alone). pgvector comes first:
    # node embeddings are vector(768).
    import cortex_memory.models  # noqa: F401  (registers the ORM classes)
    from cortex_memory.db import Base

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)
    for sql in _STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be downgraded.")
