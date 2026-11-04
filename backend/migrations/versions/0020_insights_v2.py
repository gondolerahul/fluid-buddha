"""Insights v2 + weekly digest (M2-5).

Each visitor turn is classified in the background: objections (by type),
competitors mentioned, a feature request, a buying signal. The weekly digest
has per-account settings, recipients who unsubscribed, and per-recipient
unsubscribe tokens.

Revision ID: 0020_insights_v2
Revises: 0019_experiment_variants
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0020_insights_v2"
down_revision = "0019_experiment_variants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation_turns ADD COLUMN objections text[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN competitors text[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN feature_request text")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN buying_signal boolean NOT NULL DEFAULT false")
    # NULL until the background classifier has looked at the turn.
    op.execute("ALTER TABLE conversation_turns ADD COLUMN classified_at timestamptz")
    op.execute("CREATE INDEX conversation_turns_unclassified ON conversation_turns (created_at) "
               "WHERE classified_at IS NULL")
    op.execute("CREATE INDEX conversation_turns_site_time ON conversation_turns (site_key, created_at)")

    # No row: the digest goes to the account's Owners, on Mondays at 9:00 India time.
    op.execute("""
        CREATE TABLE digest_settings (
            tenant_id   uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            enabled     boolean NOT NULL DEFAULT true,
            recipients  text[] NOT NULL DEFAULT '{}',
            timezone    text NOT NULL DEFAULT 'Asia/Kolkata',
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    # One digest per account and ISO week (also guarded by the outbox idem key).
    op.execute("""
        CREATE TABLE digest_runs (
            tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            week        text NOT NULL,
            sent_to     integer NOT NULL DEFAULT 0,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, week)
        )
    """)
    op.execute("""
        CREATE TABLE digest_unsubscribes (
            tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email       text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, email)
        )
    """)
    # The link in each digest carries a random token, not the address.
    op.execute("""
        CREATE TABLE digest_tokens (
            token       text PRIMARY KEY,
            tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email       text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, email)
        )
    """)


def downgrade() -> None:
    for t in ("digest_tokens", "digest_unsubscribes", "digest_runs", "digest_settings"):
        op.execute(f"DROP TABLE IF EXISTS {t}")
    op.execute("DROP INDEX IF EXISTS conversation_turns_site_time")
    op.execute("DROP INDEX IF EXISTS conversation_turns_unclassified")
    for col in ("classified_at", "buying_signal", "feature_request", "competitors", "objections"):
        op.execute(f"ALTER TABLE conversation_turns DROP COLUMN IF EXISTS {col}")
