"""Store each cached answer's grounding so replays show their sources (WS8).

Revision ID: 0002_cache_grounding
Revises: 0001_baseline
Create Date: 2026-11-03
"""
from __future__ import annotations

from alembic import op

revision = "0002_cache_grounding"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation_cache ADD COLUMN IF NOT EXISTS grounding jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE conversation_cache DROP COLUMN IF EXISTS grounding")
