"""Free-form pages, G3 (Phase 4 of the generative experience plan).

``site_routes``      + ``mode`` (composed | freeform) and ``pinned_regions``.
``fragment_cache``   reusable regions the G3 planner assembles pages from.
``site_experience``  + free-form switch, budgets, review share, blocked patterns.
``g3_usage``         fresh model plans per day and visitor (the budget).
``review_samples``   sampled / flagged G3 pages for the review feed.
``experiments``      + the ``freeform`` test subject.

Revision ID: 0037_freeform
Revises: 0036_taste_profiles
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0037_freeform"
down_revision = "0036_taste_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE site_routes ADD COLUMN mode text NOT NULL DEFAULT 'composed' "
               "CHECK (mode IN ('composed', 'freeform'))")
    op.execute("ALTER TABLE site_routes ADD COLUMN pinned_regions jsonb NOT NULL DEFAULT '[]'::jsonb")
    op.execute("""
        CREATE TABLE fragment_cache (
            id               uuid PRIMARY KEY,
            site_key         text NOT NULL,
            fingerprint      text NOT NULL,
            purpose          text NOT NULL,
            component        text NOT NULL,
            region           jsonb NOT NULL,
            conditions       jsonb NOT NULL DEFAULT '{}'::jsonb,
            content_version  text NOT NULL DEFAULT '',
            manifest_version integer,
            status           text NOT NULL DEFAULT 'auto' CHECK (status IN ('auto', 'pinned', 'blocked')),
            source           text NOT NULL DEFAULT 'model',
            hit_count        integer NOT NULL DEFAULT 0,
            rewards          integer NOT NULL DEFAULT 0,
            created_at       timestamptz NOT NULL DEFAULT now(),
            last_hit_at      timestamptz,
            UNIQUE (site_key, fingerprint)
        )
    """)
    op.execute("CREATE INDEX fragment_cache_purpose ON fragment_cache (site_key, purpose, status)")
    op.execute("ALTER TABLE site_experience ADD COLUMN freeform_enabled boolean NOT NULL DEFAULT true")
    op.execute("ALTER TABLE site_experience ADD COLUMN g3_daily_budget integer NOT NULL DEFAULT 200 "
               "CHECK (g3_daily_budget BETWEEN 0 AND 100000)")
    op.execute("ALTER TABLE site_experience ADD COLUMN g3_visitor_budget integer NOT NULL DEFAULT 3 "
               "CHECK (g3_visitor_budget BETWEEN 0 AND 50)")
    op.execute("ALTER TABLE site_experience ADD COLUMN review_sample_pct integer NOT NULL DEFAULT 5 "
               "CHECK (review_sample_pct BETWEEN 0 AND 100)")
    op.execute("ALTER TABLE site_experience ADD COLUMN g3_blocked_patterns text[] NOT NULL "
               "DEFAULT ARRAY['/checkout*', '/cart*', '/legal*', '/terms*', '/privacy*']")
    op.execute("""
        CREATE TABLE g3_usage (
            site_key  text NOT NULL,
            day       date NOT NULL,
            visitor   text NOT NULL,
            fresh     integer NOT NULL DEFAULT 0,
            PRIMARY KEY (site_key, day, visitor)
        )
    """)
    op.execute("""
        CREATE TABLE review_samples (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            route       text NOT NULL,
            plan_row    uuid REFERENCES plan_cache(id) ON DELETE SET NULL,
            plan        jsonb NOT NULL,
            flags       text[] NOT NULL DEFAULT '{}',
            status      text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'ok', 'flagged')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            reviewed_by text
        )
    """)
    op.execute("CREATE INDEX review_samples_site ON review_samples (site_key, status, created_at DESC)")
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_subject_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_subject_check
            CHECK (subject IN ('greeting', 'trigger', 'tour', 'persona', 'design', 'regions', 'freeform'))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM experiments WHERE subject = 'freeform'")
    op.execute("ALTER TABLE experiments DROP CONSTRAINT IF EXISTS experiments_subject_check")
    op.execute("""
        ALTER TABLE experiments ADD CONSTRAINT experiments_subject_check
            CHECK (subject IN ('greeting', 'trigger', 'tour', 'persona', 'design', 'regions'))
    """)
    op.execute("DROP TABLE IF EXISTS review_samples")
    op.execute("DROP TABLE IF EXISTS g3_usage")
    for col in ("g3_blocked_patterns", "review_sample_pct", "g3_visitor_budget", "g3_daily_budget",
                "freeform_enabled"):
        op.execute(f"ALTER TABLE site_experience DROP COLUMN IF EXISTS {col}")
    op.execute("DROP TABLE IF EXISTS fragment_cache")
    op.execute("ALTER TABLE site_routes DROP COLUMN IF EXISTS pinned_regions")
    op.execute("ALTER TABLE site_routes DROP COLUMN IF EXISTS mode")
