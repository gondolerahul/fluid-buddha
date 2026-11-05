"""The licence installed in the console of a self-hosted install (M3-5).

One row (id = 1): the signed token, when and by whom it was installed. The
token is verified offline on every read; an invalid one is refused before it
is stored.

Revision ID: 0030_install_licence
Revises: 0029_campaigns
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0030_install_licence"
down_revision = "0029_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE install_licence (
            id            integer PRIMARY KEY CHECK (id = 1),
            token         text NOT NULL,
            installed_at  timestamptz NOT NULL DEFAULT now(),
            installed_by  uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS install_licence")
