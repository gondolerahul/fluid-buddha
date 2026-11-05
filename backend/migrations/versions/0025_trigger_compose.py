"""Proactive triggers that let the agent write the message (M2-3 follow-up).

``trigger_rules.compose``: instead of the fixed message, the agent writes one
short opener for the page the visitor is on (the fixed message stays as the
fallback). ``trigger_messages`` caches what was written per rule, page and
language, so it costs one model call per page, not one per visitor.

Revision ID: 0025_trigger_compose
Revises: 0024_security
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0025_trigger_compose"
down_revision = "0024_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE trigger_rules ADD COLUMN compose boolean NOT NULL DEFAULT false")
    op.execute("""
        CREATE TABLE trigger_messages (
            rule_id     uuid NOT NULL REFERENCES trigger_rules(id) ON DELETE CASCADE,
            page        text NOT NULL,
            lang        text NOT NULL DEFAULT 'en',
            message     text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (rule_id, page, lang)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trigger_messages")
    op.execute("ALTER TABLE trigger_rules DROP COLUMN IF EXISTS compose")
