"""Adaptive regions, G1 (Phase 1 of the generative experience plan).

``site_experience``      per-site switch for generated regions.
``site_regions``         the slots an owner declares (``<fb-region name>``).
``site_intent_families`` the visitor goals a site plans for, with match rules.
``plan_cache``           G1 plans by cache key; pinned / blocked like answers.

Revision ID: 0033_adaptive_regions
Revises: 0032_experience_config
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0033_adaptive_regions"
down_revision = "0032_experience_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE site_experience (
            site_key        text PRIMARY KEY,
            regions_enabled boolean NOT NULL DEFAULT true,
            updated_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE site_regions (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            name        text NOT NULL,
            label       text NOT NULL DEFAULT '',
            purpose     text NOT NULL DEFAULT '',
            components  text[] NOT NULL DEFAULT '{}',
            pages       text[] NOT NULL DEFAULT '{}',
            enabled     boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, name)
        )
    """)
    op.execute("""
        CREATE TABLE site_intent_families (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            slug        text NOT NULL,
            label       text NOT NULL,
            description text NOT NULL DEFAULT '',
            stage       text NOT NULL DEFAULT '',
            rules       jsonb NOT NULL DEFAULT '{}'::jsonb,
            priority    integer NOT NULL DEFAULT 0,
            enabled     boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, slug)
        )
    """)
    op.execute("""
        CREATE TABLE plan_cache (
            id               uuid PRIMARY KEY,
            site_key         text NOT NULL,
            cache_key        text NOT NULL,
            family           text NOT NULL,
            persona          text NOT NULL DEFAULT '',
            lang             text NOT NULL DEFAULT 'en',
            page             text NOT NULL DEFAULT '/',
            regions          text NOT NULL,
            content_version  text NOT NULL DEFAULT '',
            manifest_version integer,
            plan             jsonb NOT NULL,
            composer         text NOT NULL DEFAULT 'rules',
            status           text NOT NULL DEFAULT 'auto' CHECK (status IN ('auto', 'pinned', 'blocked')),
            hit_count        integer NOT NULL DEFAULT 0,
            build_ms         integer NOT NULL DEFAULT 0,
            created_at       timestamptz NOT NULL DEFAULT now(),
            last_hit_at      timestamptz,
            UNIQUE (site_key, cache_key)
        )
    """)
    op.execute("CREATE INDEX plan_cache_lookup ON plan_cache (site_key, family, page, regions, status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS plan_cache")
    op.execute("DROP TABLE IF EXISTS site_intent_families")
    op.execute("DROP TABLE IF EXISTS site_regions")
    op.execute("DROP TABLE IF EXISTS site_experience")
