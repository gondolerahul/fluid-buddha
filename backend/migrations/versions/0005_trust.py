"""Trust layer (WS8): per-site privacy settings, golden-answer status on cached
answers, and when a visitor consented to the microphone.

Revision ID: 0005_trust
Revises: 0004_leads
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0005_trust"
down_revision = "0004_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Retention is in days; 0 keeps data until it is deleted by hand.
    op.execute("""
        CREATE TABLE site_privacy (
            site_key                  text PRIMARY KEY,
            redact_pii                boolean NOT NULL DEFAULT true,
            consent_required          boolean NOT NULL DEFAULT true,
            privacy_policy_url        text,
            transcript_retention_days integer NOT NULL DEFAULT 90,
            lead_retention_days       integer NOT NULL DEFAULT 0,
            updated_at                timestamptz NOT NULL DEFAULT now()
        )
    """)
    # auto: replayed by similarity; pinned: the tenant's approved answer, always
    # replayed and kept; blocked: never replayed, the question is answered fresh.
    op.execute("""
        ALTER TABLE conversation_cache
            ADD COLUMN status text NOT NULL DEFAULT 'auto'
            CHECK (status IN ('auto', 'pinned', 'blocked'))
    """)
    op.execute("ALTER TABLE conversations ADD COLUMN consent_at timestamptz")
    op.execute("CREATE INDEX conversations_site_last ON conversations (site_key, last_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS conversations_site_last")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS consent_at")
    op.execute("ALTER TABLE conversation_cache DROP COLUMN IF EXISTS status")
    op.execute("DROP TABLE IF EXISTS site_privacy")
