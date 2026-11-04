"""Time to first audio per voice turn (F-3): question received to the first
byte of speech sent back.

Revision ID: 0008_ttfa
Revises: 0007_experiments
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0008_ttfa"
down_revision = "0007_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Null for text turns and text-only (Basic) voice turns: nothing was spoken.
    op.execute("ALTER TABLE usage_events ADD COLUMN ttfa_ms double precision")


def downgrade() -> None:
    op.execute("ALTER TABLE usage_events DROP COLUMN IF EXISTS ttfa_ms")
