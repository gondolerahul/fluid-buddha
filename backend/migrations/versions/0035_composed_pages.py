"""Composed pages, G2 (Phase 2 of the generative experience plan).

``site_routes``      the route registry (templated patterns, canonical plan).
``site_entities``    structured records pages bind to (``entity:<Type>``).
``site_connectors``  content feeds that fill entities (JSON feed, WordPress).

Page plans are stored in ``plan_cache`` with the region set ``@page``.

Revision ID: 0035_composed_pages
Revises: 0034_region_test_subject
Create Date: 2026-11-06
"""
from __future__ import annotations

from alembic import op

revision = "0035_composed_pages"
down_revision = "0034_region_test_subject"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE site_routes (
            id              uuid PRIMARY KEY,
            site_key        text NOT NULL,
            pattern         text NOT NULL,
            title           text NOT NULL DEFAULT '',
            purpose         text NOT NULL DEFAULT '',
            enabled         boolean NOT NULL DEFAULT true,
            priority        integer NOT NULL DEFAULT 0,
            canonical_plan  uuid REFERENCES plan_cache(id) ON DELETE SET NULL,
            created_at      timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, pattern)
        )
    """)
    op.execute("""
        CREATE TABLE site_entities (
            id          uuid PRIMARY KEY,
            site_key    text NOT NULL,
            type        text NOT NULL,
            key         text NOT NULL,
            data        jsonb NOT NULL,
            source      text NOT NULL DEFAULT 'manual',
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, type, key)
        )
    """)
    op.execute("CREATE INDEX site_entities_type ON site_entities (site_key, type)")
    op.execute("""
        CREATE TABLE site_connectors (
            id            uuid PRIMARY KEY,
            site_key      text NOT NULL,
            kind          text NOT NULL CHECK (kind IN ('json_feed', 'wordpress')),
            name          text NOT NULL DEFAULT '',
            url           text NOT NULL,
            entity_type   text NOT NULL,
            config        jsonb NOT NULL DEFAULT '{}'::jsonb,
            last_sync_at  timestamptz,
            last_status   text NOT NULL DEFAULT '',
            created_at    timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_connectors")
    op.execute("DROP TABLE IF EXISTS site_entities")
    op.execute("DROP TABLE IF EXISTS site_routes")
