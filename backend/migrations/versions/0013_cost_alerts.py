"""Per-site cost alerts (F-3): a daily AI-cost threshold per site, and a record
of each alert sent so it goes out once per site, day and kind.

Revision ID: 0013_cost_alerts
Revises: 0012_experiment_bots
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0013_cost_alerts"
down_revision = "0012_experiment_bots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = no threshold of the site's own (the daily cap still alerts).
    op.execute("ALTER TABLE site_integrations ADD COLUMN cost_alert_usd double precision")
    # level: threshold (the site's own) | cap_80 | cap_100 (of the daily spend cap).
    op.execute("""
        CREATE TABLE cost_alerts (
            site_key   text NOT NULL,
            day        date NOT NULL,
            level      text NOT NULL CHECK (level IN ('threshold', 'cap_80', 'cap_100')),
            spent_usd  double precision NOT NULL,
            limit_usd  double precision NOT NULL,
            delivered  boolean NOT NULL DEFAULT false,
            error      text,
            at         timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (site_key, day, level)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cost_alerts")
    op.execute("ALTER TABLE site_integrations DROP COLUMN IF EXISTS cost_alert_usd")
