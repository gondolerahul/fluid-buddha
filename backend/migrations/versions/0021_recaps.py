"""Shareable recap pages (M2-6).

A recap is a snapshot of one conversation (summary, answers, the components
shown, sources, next steps) behind an unguessable token. It goes with its
conversation (retention, erasure, site deletion) and expires after the site's
``recap_days``. Views are counted per viewer (a cookie id), so forwards show
up as new viewers.

Revision ID: 0021_recaps
Revises: 0020_insights_v2
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0021_recaps"
down_revision = "0020_insights_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation_turns ADD COLUMN components jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE site_privacy ADD COLUMN recap_days integer NOT NULL DEFAULT 90")
    op.execute("""
        CREATE TABLE recaps (
            id               uuid PRIMARY KEY,
            token            text NOT NULL UNIQUE,
            site_key         text NOT NULL,
            conversation_id  uuid NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
            content          jsonb NOT NULL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            updated_at       timestamptz NOT NULL DEFAULT now(),
            expires_at       timestamptz NOT NULL,
            views            integer NOT NULL DEFAULT 0,
            viewers          integer NOT NULL DEFAULT 0,
            last_viewed_at   timestamptz
        )
    """)
    op.execute("CREATE INDEX recaps_site ON recaps (site_key, created_at DESC)")
    op.execute("""
        CREATE TABLE recap_views (
            recap_id   uuid NOT NULL REFERENCES recaps(id) ON DELETE CASCADE,
            viewer     text NOT NULL,
            views      integer NOT NULL DEFAULT 1,
            first_at   timestamptz NOT NULL DEFAULT now(),
            last_at    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (recap_id, viewer)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recap_views")
    op.execute("DROP TABLE IF EXISTS recaps")
    op.execute("ALTER TABLE site_privacy DROP COLUMN IF EXISTS recap_days")
    op.execute("ALTER TABLE conversation_turns DROP COLUMN IF EXISTS components")
