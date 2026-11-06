"""Personal experience (Phase 3 of the generative experience plan).

``taste_profiles``   a remembered visitor's taste (only with memory opt-in: the
                     foreign key to ``visitor_memories`` removes it with their memory).
``plan_cache``       + ``taste`` bucket, bandit ``arm`` / ``base_key`` / ``rewards``.
``plan_feedback``    one reward per visitor, plan and event.
``site_experience``  + bandit settings.

Revision ID: 0036_taste_profiles
Revises: 0035_composed_pages
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0036_taste_profiles"
down_revision = "0035_composed_pages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE taste_profiles (
            site_key    text NOT NULL,
            visitor_id  text NOT NULL,
            dims        jsonb NOT NULL DEFAULT '{}'::jsonb,
            interests   jsonb NOT NULL DEFAULT '{}'::jsonb,
            updated_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (site_key, visitor_id),
            FOREIGN KEY (site_key, visitor_id) REFERENCES visitor_memories (site_key, visitor_id)
                ON DELETE CASCADE
        )
    """)
    op.execute("ALTER TABLE plan_cache ADD COLUMN taste text NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE plan_cache ADD COLUMN arm integer NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE plan_cache ADD COLUMN base_key text NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE plan_cache ADD COLUMN rewards integer NOT NULL DEFAULT 0")
    op.execute("UPDATE plan_cache SET base_key = cache_key")
    op.execute("CREATE INDEX plan_cache_arms ON plan_cache (site_key, base_key)")
    op.execute("""
        CREATE TABLE plan_feedback (
            site_key    text NOT NULL,
            plan_row    uuid NOT NULL REFERENCES plan_cache(id) ON DELETE CASCADE,
            visitor     text NOT NULL,
            event       text NOT NULL CHECK (event IN ('engage', 'convert')),
            at          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (plan_row, visitor, event)
        )
    """)
    op.execute("ALTER TABLE site_experience ADD COLUMN bandit_enabled boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE site_experience ADD COLUMN max_arms integer NOT NULL DEFAULT 2 "
               "CHECK (max_arms BETWEEN 1 AND 3)")
    op.execute("ALTER TABLE site_experience ADD COLUMN explore_pct integer NOT NULL DEFAULT 10 "
               "CHECK (explore_pct BETWEEN 0 AND 50)")


def downgrade() -> None:
    op.execute("ALTER TABLE site_experience DROP COLUMN IF EXISTS explore_pct")
    op.execute("ALTER TABLE site_experience DROP COLUMN IF EXISTS max_arms")
    op.execute("ALTER TABLE site_experience DROP COLUMN IF EXISTS bandit_enabled")
    op.execute("DROP TABLE IF EXISTS plan_feedback")
    op.execute("DROP INDEX IF EXISTS plan_cache_arms")
    for col in ("rewards", "base_key", "arm", "taste"):
        op.execute(f"ALTER TABLE plan_cache DROP COLUMN IF EXISTS {col}")
    op.execute("DROP TABLE IF EXISTS taste_profiles")
