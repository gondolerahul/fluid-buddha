"""Agent endpoint: MCP + llms.txt (M3-2).

``tenant_websites.agent_access``: whether AI assistants may query the site
through its MCP endpoint, llms.txt and REST ``ask`` (off by default).

``agent_tokens``: tokens the customer issues to an assistant for the tools
that do something (capture a lead, run an action); only a hash is stored.

``agent_requests``: every call from an assistant — what it asked for, from
which client, with which token, and whether it worked — for the console's
"agent traffic" and analytics.

Revision ID: 0027_agent_access
Revises: 0026_model_providers
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0027_agent_access"
down_revision = "0026_model_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_websites ADD COLUMN agent_access boolean NOT NULL DEFAULT false")
    op.execute("""
        CREATE TABLE agent_tokens (
            id            uuid PRIMARY KEY,
            site_key      text NOT NULL,
            name          text NOT NULL,
            token_hash    text NOT NULL UNIQUE,
            scopes        text[] NOT NULL DEFAULT '{}',
            created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at    timestamptz NOT NULL DEFAULT now(),
            last_used_at  timestamptz,
            revoked_at    timestamptz
        )
    """)
    op.execute("CREATE INDEX agent_tokens_site ON agent_tokens (site_key)")
    op.execute("""
        CREATE TABLE agent_requests (
            id         bigserial PRIMARY KEY,
            site_key   text NOT NULL,
            kind       text NOT NULL,            -- mcp | rest | llms
            tool       text,
            client     text,
            token_id   uuid,
            ok         boolean NOT NULL DEFAULT true,
            error      text,
            at         timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX agent_requests_site_time ON agent_requests (site_key, at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_requests")
    op.execute("DROP TABLE IF EXISTS agent_tokens")
    op.execute("ALTER TABLE tenant_websites DROP COLUMN IF EXISTS agent_access")
