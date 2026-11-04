"""SSO domains must be proven (M2-1): an account's identity provider may only
sign in people whose email domain that account has verified with a DNS TXT
record. Otherwise anyone could claim a company's domain, point it at their own
identity provider and sign in as that company's people.

Replaces ``tenant_sso.allowed_domains`` with ``sso_domains`` (one account per
domain).

Revision ID: 0016_sso_domains
Revises: 0015_teams
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0016_sso_domains"
down_revision = "0015_teams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sso_domains (
            domain        text PRIMARY KEY,
            tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            token         text NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now(),
            verified_at   timestamptz
        )
    """)
    op.execute("CREATE INDEX sso_domains_tenant ON sso_domains (tenant_id)")
    op.execute("ALTER TABLE tenant_sso DROP COLUMN allowed_domains")


def downgrade() -> None:
    op.execute("ALTER TABLE tenant_sso ADD COLUMN allowed_domains text[] NOT NULL DEFAULT '{}'")
    op.execute("DROP TABLE IF EXISTS sso_domains")
