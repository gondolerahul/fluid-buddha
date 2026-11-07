"""Generative experience Phase 5 (agent-ready): views, agent confirmations, task analytics.

* ``agent_requests`` + ``plan_id`` / ``action`` — which view and action an agent call
  touched (task-completion analytics).
* ``agent_confirmations`` — one-time codes for actions whose agent policy is
  ``confirm``: the agent's human approves, the agent calls again with the code
  (same inputs, within the expiry, once).

Revision ID: 0038_agent_ready
Revises: 0037_freeform
Create Date: 2026-11-07
"""
from __future__ import annotations

from alembic import op

revision = "0038_agent_ready"
down_revision = "0037_freeform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_requests ADD COLUMN IF NOT EXISTS plan_id text")
    op.execute("ALTER TABLE agent_requests ADD COLUMN IF NOT EXISTS action text")
    op.execute("""
        CREATE TABLE agent_confirmations (
            code_hash   text PRIMARY KEY,
            site_key    text NOT NULL,
            plan_id     text NOT NULL,
            action      text NOT NULL,
            inputs_hash text NOT NULL,
            token_id    uuid,
            summary     text NOT NULL DEFAULT '',
            expires_at  timestamptz NOT NULL,
            used_at     timestamptz,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX agent_confirmations_site ON agent_confirmations (site_key, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_confirmations")
    op.execute("ALTER TABLE agent_requests DROP COLUMN IF EXISTS action")
    op.execute("ALTER TABLE agent_requests DROP COLUMN IF EXISTS plan_id")
