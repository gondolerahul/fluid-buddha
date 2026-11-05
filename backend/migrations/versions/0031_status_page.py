"""Public status page (M3-6).

``status_samples``: one row per component per probe (every minute, from the
same readiness checks the load balancer uses): up / degraded / down, kept 100
days — the 90-day uptime bars.

``status_incidents`` / ``status_updates``: what operators post during an
incident (investigating → identified → monitoring → resolved) or ahead of
maintenance, shown on the page.

Revision ID: 0031_status_page
Revises: 0030_install_licence
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0031_status_page"
down_revision = "0030_install_licence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE status_samples (
            id          bigserial PRIMARY KEY,
            at          timestamptz NOT NULL DEFAULT now(),
            component   text NOT NULL,
            state       text NOT NULL CHECK (state IN ('up', 'degraded', 'down')),
            detail      text
        )
    """)
    op.execute("CREATE INDEX status_samples_component_at ON status_samples (component, at)")
    op.execute("""
        CREATE TABLE status_incidents (
            id          uuid PRIMARY KEY,
            title       text NOT NULL,
            impact      text NOT NULL CHECK (impact IN ('minor', 'major', 'critical', 'maintenance')),
            status      text NOT NULL CHECK (status IN ('investigating', 'identified', 'monitoring', 'resolved', 'scheduled')),
            components  text[] NOT NULL DEFAULT '{}',
            created_at  timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE status_updates (
            id          bigserial PRIMARY KEY,
            incident_id uuid NOT NULL REFERENCES status_incidents(id) ON DELETE CASCADE,
            status      text NOT NULL,
            body        text NOT NULL,
            at          timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS status_updates")
    op.execute("DROP TABLE IF EXISTS status_incidents")
    op.execute("DROP TABLE IF EXISTS status_samples")
