"""Bring your own model (M3-4).

``model_providers``: an account's own model provider — Anthropic, OpenAI or
Azure OpenAI — with the models it uses for the fast and the thinking roles,
its API key (encrypted with SECRETS_KEY), Azure's endpoint and API version,
optional prices for cost tracking, and the last connection test.

``tenant_websites.byo_model``: whether a site uses the account's provider
(on by default once one is set up) or the platform's.

``usage_events.provider`` / ``byo_llm_cost``: which provider served a turn,
and the part of its cost the account pays its provider directly (kept out
of the platform's daily spend cap).

Revision ID: 0026_model_providers
Revises: 0025_trigger_compose
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0026_model_providers"
down_revision = "0025_trigger_compose"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE model_providers (
            tenant_id      uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            provider       text NOT NULL CHECK (provider IN ('anthropic', 'openai', 'azure_openai')),
            fast_model     text NOT NULL,
            thinker_model  text NOT NULL,
            api_key_enc    text NOT NULL,
            endpoint       text,
            api_version    text,
            prices         jsonb NOT NULL DEFAULT '{}'::jsonb,
            enabled        boolean NOT NULL DEFAULT true,
            last_test_at   timestamptz,
            last_test_ok   boolean,
            last_error     text,
            updated_at     timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE tenant_websites ADD COLUMN byo_model boolean NOT NULL DEFAULT true")
    op.execute("ALTER TABLE usage_events ADD COLUMN provider text NOT NULL DEFAULT 'platform'")
    op.execute("ALTER TABLE usage_events ADD COLUMN byo_llm_cost double precision NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE usage_events DROP COLUMN IF EXISTS byo_llm_cost")
    op.execute("ALTER TABLE usage_events DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE tenant_websites DROP COLUMN IF EXISTS byo_model")
    op.execute("DROP TABLE IF EXISTS model_providers")
