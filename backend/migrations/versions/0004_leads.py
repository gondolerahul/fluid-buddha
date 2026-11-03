"""Revenue layer v1 (WS7): leads captured by the widget, and each site's
outbound integrations (signed webhook, Slack hot-lead alerts).

Revision ID: 0004_leads
Revises: 0003_conversations
Create Date: 2026-11-03
"""
from __future__ import annotations

from alembic import op

revision = "0004_leads"
down_revision = "0003_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE leads (
            id              uuid PRIMARY KEY,
            site_key        text NOT NULL,
            session_id      text,
            conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
            source          text NOT NULL DEFAULT 'form',
            name            text,
            email           text NOT NULL,
            company         text,
            phone           text,
            message         text,
            interest        text,
            persona         text,
            score           integer NOT NULL DEFAULT 0,
            summary         text NOT NULL DEFAULT '',
            status          text NOT NULL DEFAULT 'new',
            delivered_at    timestamptz,
            delivery_error  text,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX leads_site_time ON leads (site_key, created_at)")
    op.execute("""
        CREATE TABLE site_integrations (
            site_key          text PRIMARY KEY,
            webhook_url       text,
            webhook_secret    text NOT NULL,
            slack_webhook_url text,
            hot_lead_score    integer NOT NULL DEFAULT 60,
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_integrations")
    op.execute("DROP TABLE IF EXISTS leads")
