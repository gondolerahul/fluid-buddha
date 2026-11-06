"""Actions marketplace + custom components (M2-8).

``site_actions``: what the agent may do on a site (take a payment by Razorpay
link, request a quote, start a trial, book a meeting, call a webhook), each
with typed inputs, its settings and its secret (encrypted).

``action_runs``: every time the agent proposes an action. Nothing happens
until the visitor confirms it; the run then holds the outcome (a payment link,
a login link…), and a payment link's run turns ``paid`` when Razorpay says so.

``site_components``: components a tenant registers — a declarative template
over the built-in components, or a sandboxed iframe — that the agent can show.

Leads gain ``paid_at`` / ``paid_amount`` (paise) for the paid status.

Revision ID: 0023_actions
Revises: 0022_languages
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0023_actions"
down_revision = "0022_languages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE site_actions (
            id           uuid PRIMARY KEY,
            site_key     text NOT NULL,
            kind         text NOT NULL CHECK (kind IN
                           ('payment_link', 'quote_request', 'trial', 'meeting_link', 'webhook')),
            name         text NOT NULL,
            label        text NOT NULL,
            description  text NOT NULL DEFAULT '',
            enabled      boolean NOT NULL DEFAULT true,
            config       jsonb NOT NULL DEFAULT '{}'::jsonb,
            secret_enc   text,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, name)
        )
    """)
    op.execute("""
        CREATE TABLE action_runs (
            id           uuid PRIMARY KEY,
            site_key     text NOT NULL,
            action_id    uuid REFERENCES site_actions(id) ON DELETE SET NULL,
            action_name  text NOT NULL,
            kind         text NOT NULL,
            session_id   text NOT NULL,
            status       text NOT NULL DEFAULT 'proposed' CHECK (status IN
                           ('proposed', 'cancelled', 'expired', 'done', 'failed', 'paid')),
            inputs       jsonb NOT NULL DEFAULT '{}'::jsonb,
            summary      jsonb NOT NULL DEFAULT '[]'::jsonb,
            amount       integer,
            currency     text,
            result       jsonb NOT NULL DEFAULT '{}'::jsonb,
            error        text,
            external_id  text,
            lead_id      uuid REFERENCES leads(id) ON DELETE SET NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            confirmed_at timestamptz,
            finished_at  timestamptz,
            paid_at      timestamptz
        )
    """)
    op.execute("CREATE INDEX action_runs_site_time ON action_runs (site_key, created_at DESC)")
    op.execute("CREATE INDEX action_runs_session ON action_runs (site_key, session_id)")
    op.execute("CREATE INDEX action_runs_external ON action_runs (external_id) "
               "WHERE external_id IS NOT NULL")
    op.execute("""
        CREATE TABLE site_components (
            id           uuid PRIMARY KEY,
            site_key     text NOT NULL,
            name         text NOT NULL,
            label        text NOT NULL,
            description  text NOT NULL DEFAULT '',
            kind         text NOT NULL CHECK (kind IN ('template', 'iframe')),
            props_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
            template     jsonb,
            iframe_url   text,
            enabled      boolean NOT NULL DEFAULT true,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_key, name)
        )
    """)
    op.execute("ALTER TABLE leads ADD COLUMN paid_at timestamptz")
    op.execute("ALTER TABLE leads ADD COLUMN paid_amount integer")


def downgrade() -> None:
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS paid_amount")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS paid_at")
    op.execute("DROP TABLE IF EXISTS site_components")
    op.execute("DROP TABLE IF EXISTS action_runs")
    op.execute("DROP TABLE IF EXISTS site_actions")
