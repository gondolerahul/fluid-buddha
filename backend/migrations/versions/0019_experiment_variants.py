"""Experimentation engine (M2-4): runs that test N variants of one setting.

A run either measures the agent against a holdout (WS11: ``subject`` NULL,
arms ``agent``/``holdout``) or tests 2-4 variants of one thing — the
greeting, the proactive triggers, the tour, the starting persona or the
design level — optionally keeping a holdout too (arms ``a``..``d`` and
``holdout``).

Revision ID: 0019_experiment_variants
Revises: 0018_triggers
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0019_experiment_variants"
down_revision = "0018_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE experiments ADD COLUMN name text")
    op.execute("""
        ALTER TABLE experiments ADD COLUMN subject text
            CHECK (subject IN ('greeting', 'trigger', 'tour', 'persona', 'design'))
    """)
    # [{key, label, overrides}], the control first. Empty for a holdout run.
    op.execute("ALTER TABLE experiments ADD COLUMN variants jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE experiments ADD COLUMN winner text")
    op.execute("ALTER TABLE experiments ADD COLUMN promoted_at timestamptz")
    # A variant test may run without a holdout.
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_holdout_pct_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_holdout_pct_check
            CHECK (holdout_pct BETWEEN 0 AND 50)
    """)
    op.execute("ALTER TABLE experiment_visitors DROP CONSTRAINT IF EXISTS experiment_visitors_arm_check")
    op.execute("""
        ALTER TABLE experiment_visitors ADD CONSTRAINT experiment_visitors_arm_check
            CHECK (arm IN ('agent', 'holdout', 'a', 'b', 'c', 'd'))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM experiments WHERE subject IS NOT NULL")
    op.execute("ALTER TABLE experiment_visitors DROP CONSTRAINT IF EXISTS experiment_visitors_arm_check")
    op.execute("""
        ALTER TABLE experiment_visitors ADD CONSTRAINT experiment_visitors_arm_check
            CHECK (arm IN ('agent', 'holdout'))
    """)
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_holdout_pct_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_holdout_pct_check
            CHECK (holdout_pct BETWEEN 1 AND 50)
    """)
    for col in ("promoted_at", "winner", "variants", "subject", "name"):
        op.execute(f"ALTER TABLE experiments DROP COLUMN IF EXISTS {col}")
