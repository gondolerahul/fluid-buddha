"""Generative experience configuration (P0-7).

``site_design_systems``: the design system an owner manages in the console
(tokens, tunables, brand voice). One current row per site; it takes precedence
over a design-system file and the tokens extracted at onboarding.

``site_component_manifests``: versions of the site's component manifest. A
version starts as a ``draft`` (typed in, or generated from Storybook or the
live site, P0-9) and becomes ``approved`` when an Admin approves it; approving
archives the previously approved version. An approved version is immutable.
Only the approved version reaches the planner.

Revision ID: 0032_experience_config
Revises: 0031_status_page
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0032_experience_config"
down_revision = "0031_status_page"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE site_design_systems (
            site_key    text PRIMARY KEY,
            data        jsonb NOT NULL,
            updated_at  timestamptz NOT NULL DEFAULT now(),
            updated_by  text
        )
    """)
    op.execute("""
        CREATE TABLE site_component_manifests (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            version     integer NOT NULL,
            status      text NOT NULL CHECK (status IN ('draft', 'approved', 'archived')),
            source      text NOT NULL DEFAULT 'manual'
                        CHECK (source IN ('manual', 'storybook', 'site', 'file')),
            data        jsonb NOT NULL,
            notes       text NOT NULL DEFAULT '',
            created_at  timestamptz NOT NULL DEFAULT now(),
            created_by  text,
            approved_at timestamptz,
            approved_by text,
            UNIQUE (site_key, version)
        )
    """)
    # At most one approved version per site.
    op.execute("""
        CREATE UNIQUE INDEX site_component_manifests_one_approved
            ON site_component_manifests (site_key) WHERE status = 'approved'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_component_manifests")
    op.execute("DROP TABLE IF EXISTS site_design_systems")
