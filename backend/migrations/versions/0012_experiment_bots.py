"""Holdout A/B (WS11): count the automated visits a run turned away.

Revision ID: 0012_experiment_bots
Revises: 0011_next_subscription
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0012_experiment_bots"
down_revision = "0011_next_subscription"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bots aren't enrolled (app/experiments/bots.py); this only says how many
    # enrolment attempts were refused, so the console can show it.
    op.execute("ALTER TABLE experiments ADD COLUMN bots_ignored integer NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE experiments DROP COLUMN IF EXISTS bots_ignored")
