"""Holdout A/B (WS11): experiments, the visitors assigned to each arm, and the
site-goal conversions they made.

Revision ID: 0007_experiments
Revises: 0006_onboarding
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0007_experiments"
down_revision = "0006_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per run. Changing the holdout share starts a new run, so every
    # run's numbers come from one fixed split.
    op.execute("""
        CREATE TABLE experiments (
            id           uuid PRIMARY KEY,
            site_key     text NOT NULL,
            holdout_pct  integer NOT NULL CHECK (holdout_pct BETWEEN 1 AND 50),
            goal_path    text,
            status       text NOT NULL DEFAULT 'running'
                         CHECK (status IN ('running', 'stopped')),
            started_at   timestamptz NOT NULL DEFAULT now(),
            ended_at     timestamptz
        )
    """)
    op.execute("CREATE INDEX experiments_site ON experiments (site_key, started_at DESC)")
    # Visitors are anonymous random ids made by the widget: no personal data.
    op.execute("""
        CREATE TABLE experiment_visitors (
            experiment_id       uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            visitor_id          text NOT NULL,
            arm                 text NOT NULL CHECK (arm IN ('agent', 'holdout')),
            first_seen          timestamptz NOT NULL DEFAULT now(),
            first_conversion_at timestamptz,
            conversions         integer NOT NULL DEFAULT 0,
            PRIMARY KEY (experiment_id, visitor_id)
        )
    """)
    op.execute("""
        CREATE TABLE experiment_events (
            id             bigserial PRIMARY KEY,
            experiment_id  uuid NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
            visitor_id     text NOT NULL,
            name           text NOT NULL,
            value          double precision,
            at             timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX experiment_events_exp ON experiment_events (experiment_id, at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS experiment_events")
    op.execute("DROP TABLE IF EXISTS experiment_visitors")
    op.execute("DROP TABLE IF EXISTS experiments")
