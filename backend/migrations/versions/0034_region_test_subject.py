"""Variant tests may test generated regions (Phase 1, P1-4).

Adds ``regions`` to the subjects ``experiments.subject`` allows.

Revision ID: 0034_region_test_subject
Revises: 0033_adaptive_regions
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0034_region_test_subject"
down_revision = "0033_adaptive_regions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_subject_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_subject_check
            CHECK (subject IN ('greeting', 'trigger', 'tour', 'persona', 'design', 'regions'))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM experiments WHERE subject = 'regions'")
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_subject_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_subject_check
            CHECK (subject IN ('greeting', 'trigger', 'tour', 'persona', 'design'))
    """)
