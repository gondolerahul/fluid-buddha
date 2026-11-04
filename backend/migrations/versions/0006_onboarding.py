"""Self-serve onboarding (WS9): website crawl jobs, and the design system
extracted from a site's CSS.

Revision ID: 0006_onboarding
Revises: 0005_trust
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0006_onboarding"
down_revision = "0005_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per "crawl my site" run, so the console can show progress and how
    # long paste-URL → live took.
    op.execute("""
        CREATE TABLE crawl_jobs (
            id              uuid PRIMARY KEY,
            website_id      uuid NOT NULL REFERENCES tenant_websites(id) ON DELETE CASCADE,
            start_url       text NOT NULL,
            max_pages       integer NOT NULL,
            max_depth       integer NOT NULL,
            status          text NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'done', 'failed')),
            phase           text NOT NULL DEFAULT 'crawling',
            pages_found     integer NOT NULL DEFAULT 0,
            pages_ingested  integer NOT NULL DEFAULT 0,
            pages_skipped   integer NOT NULL DEFAULT 0,
            personas_added  integer NOT NULL DEFAULT 0,
            design_found    boolean NOT NULL DEFAULT false,
            error           text,
            started_at      timestamptz NOT NULL DEFAULT now(),
            finished_at     timestamptz
        )
    """)
    op.execute("CREATE INDEX crawl_jobs_site ON crawl_jobs (website_id, started_at DESC)")
    # Brand tokens read off the site (colours, fonts, radius, logo); an owner's
    # design-system.json file still wins when one is configured.
    op.execute("""
        CREATE TABLE site_design (
            site_key    text PRIMARY KEY,
            design      jsonb NOT NULL,
            source_url  text,
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_design")
    op.execute("DROP TABLE IF EXISTS crawl_jobs")
