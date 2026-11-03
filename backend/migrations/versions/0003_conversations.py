"""Conversation-level store for Insights v1 (WS10): one row per visitor session,
one row per turn with the question, answer and whether it was grounded.

Revision ID: 0003_conversations
Revises: 0002_cache_grounding
Create Date: 2026-11-03
"""
from __future__ import annotations

from alembic import op

revision = "0003_conversations"
down_revision = "0002_cache_grounding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE conversations (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            session_id  text NOT NULL,
            channel     text NOT NULL DEFAULT 'text',
            persona     text,
            first_page  text,
            turns       integer NOT NULL DEFAULT 0,
            ungrounded  integer NOT NULL DEFAULT 0,
            started_at  timestamptz NOT NULL DEFAULT now(),
            last_at     timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, session_id)
        )
    """)
    op.execute("CREATE INDEX conversations_site_time ON conversations (site_key, started_at)")
    op.execute("""
        CREATE TABLE conversation_turns (
            id                uuid PRIMARY KEY,
            conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            site_key          text NOT NULL,
            question          text NOT NULL,
            q_norm            text NOT NULL,
            answer            text NOT NULL DEFAULT '',
            intent            text,
            persona           text,
            page              text,
            found             boolean NOT NULL DEFAULT false,
            confidence        double precision NOT NULL DEFAULT 0,
            sources           jsonb NOT NULL DEFAULT '[]'::jsonb,
            served_from_cache boolean NOT NULL DEFAULT false,
            created_at        timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX conversation_turns_conv ON conversation_turns (conversation_id, created_at)")
    op.execute("CREATE INDEX conversation_turns_site_q ON conversation_turns (site_key, q_norm)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_turns")
    op.execute("DROP TABLE IF EXISTS conversations")
