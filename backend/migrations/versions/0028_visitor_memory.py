"""Returning-visitor memory, opt-in (M3-3).

``visitor_memories``: for a visitor who said "remember me" on a site, a short
memory of their past conversations there — the topics, the components they
explored, what the agent couldn't answer, whether they left their details.
Keyed by (site, anonymous visitor id): never shared between sites. Built from
the already PII-masked transcript.

``conversations.visitor_id``: links a conversation to a visitor who opted in
(set only then), so their next visit can recall it and "forget me" can find
everything.

``site_privacy.memory_enabled`` / ``memory_days``: the site offers it (off by
default) and how long a memory is kept after the visitor's last visit.

Revision ID: 0028_visitor_memory
Revises: 0027_agent_access
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0028_visitor_memory"
down_revision = "0027_agent_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE visitor_memories (
            site_key         text NOT NULL,
            visitor_id       text NOT NULL,
            opted_in_at      timestamptz NOT NULL DEFAULT now(),
            summary          text NOT NULL DEFAULT '',
            topics           text[] NOT NULL DEFAULT '{}',
            components       text[] NOT NULL DEFAULT '{}',
            open_questions   text[] NOT NULL DEFAULT '{}',
            persona          text,
            left_details     boolean NOT NULL DEFAULT false,
            conversations    integer NOT NULL DEFAULT 0,
            lang             text NOT NULL DEFAULT 'en',
            built_at         timestamptz,
            last_seen_at     timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (site_key, visitor_id)
        )
    """)
    op.execute("ALTER TABLE conversations ADD COLUMN visitor_id text")
    op.execute("CREATE INDEX conversations_visitor ON conversations (site_key, visitor_id) "
               "WHERE visitor_id IS NOT NULL")
    op.execute("ALTER TABLE site_privacy ADD COLUMN memory_enabled boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE site_privacy ADD COLUMN memory_days integer NOT NULL DEFAULT 180")


def downgrade() -> None:
    op.execute("ALTER TABLE site_privacy DROP COLUMN IF EXISTS memory_days")
    op.execute("ALTER TABLE site_privacy DROP COLUMN IF EXISTS memory_enabled")
    op.execute("DROP INDEX IF EXISTS conversations_visitor")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS visitor_id")
    op.execute("DROP TABLE IF EXISTS visitor_memories")
