"""Generative landing pages: campaigns (M3-1).

``campaigns``: a site's landing-page brief — goal, audience, key messages,
which sections the page may use, the call to action, and the proof the
customer supplies (testimonials, logos), which the composer may only quote.
Optionally a variant B (headline, messages, CTA) split 50/50 as an
experiment. Hosted at ``/p/{site_key}/{slug}``.

``campaign_pages``: composed pages cached per (campaign version, arm,
persona, question, language, content version), so most visits cost nothing.

``campaign_events``: views, engagement and conversions per viewer and arm,
with the persona, question and UTM source the page was composed for.

Revision ID: 0029_campaigns
Revises: 0028_visitor_memory
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0029_campaigns"
down_revision = "0028_visitor_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE campaigns (
            id             uuid PRIMARY KEY,
            site_key       text NOT NULL,
            slug           text NOT NULL,
            name           text NOT NULL,
            status         text NOT NULL DEFAULT 'draft',
            goal           text NOT NULL DEFAULT '',
            audience       text NOT NULL DEFAULT '',
            persona        text,
            key_messages   text[] NOT NULL DEFAULT '{}',
            sections       text[] NOT NULL DEFAULT '{}',
            cta_label      text NOT NULL DEFAULT '',
            cta_url        text NOT NULL DEFAULT '',
            testimonials   jsonb NOT NULL DEFAULT '[]',
            logos          jsonb NOT NULL DEFAULT '[]',
            variant        jsonb,
            embed_origins  text[] NOT NULL DEFAULT '{}',
            version        integer NOT NULL DEFAULT 1,
            created_by     uuid,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT campaigns_status CHECK (status IN ('draft', 'live', 'paused')),
            CONSTRAINT campaigns_slug UNIQUE (site_key, slug)
        )
    """)
    op.execute("""
        CREATE TABLE campaign_pages (
            id           uuid PRIMARY KEY,
            campaign_id  uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            cache_key    text NOT NULL,
            arm          text NOT NULL DEFAULT 'a',
            persona      text,
            question     text,
            spec         jsonb NOT NULL,
            composer     text NOT NULL DEFAULT 'rules',
            build_ms     integer NOT NULL DEFAULT 0,
            hits         integer NOT NULL DEFAULT 0,
            created_at   timestamptz NOT NULL DEFAULT now(),
            last_hit_at  timestamptz,
            CONSTRAINT campaign_pages_key UNIQUE (campaign_id, cache_key)
        )
    """)
    op.execute("""
        CREATE TABLE campaign_events (
            id           bigserial PRIMARY KEY,
            campaign_id  uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            site_key     text NOT NULL,
            viewer       text NOT NULL,
            kind         text NOT NULL,
            arm          text NOT NULL DEFAULT 'a',
            persona      text,
            source       text,
            cached       boolean,
            created_at   timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT campaign_events_kind CHECK (kind IN ('view', 'engage', 'convert'))
        )
    """)
    op.execute("CREATE INDEX campaign_events_campaign ON campaign_events (campaign_id, kind, created_at)")
    op.execute("CREATE INDEX campaigns_site ON campaigns (site_key)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS campaign_events")
    op.execute("DROP TABLE IF EXISTS campaign_pages")
    op.execute("DROP TABLE IF EXISTS campaigns")
