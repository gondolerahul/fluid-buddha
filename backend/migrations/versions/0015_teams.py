"""Teams (M2-1): people (users) separate from accounts (tenants), their roles
in each account, invitations, an append-only audit log, per-account SSO
settings and in-flight SSO logins.

Every existing account gets one Owner whose user id is the account id and who
keeps the account's email and password, so nobody re-registers and tokens
issued before this migration keep working.

Revision ID: 0015_teams
Revises: 0014_email_outbox
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0015_teams"
down_revision = "0014_email_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # password_hash is NULL for people who only ever sign in with SSO.
    op.execute("""
        CREATE TABLE users (
            id             uuid PRIMARY KEY,
            email          text NOT NULL UNIQUE,
            name           text,
            password_hash  text,
            created_at     timestamptz NOT NULL DEFAULT now(),
            last_login_at  timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE memberships (
            user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            role        text NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, tenant_id)
        )
    """)
    op.execute("CREATE INDEX memberships_tenant ON memberships (tenant_id)")
    # Only a hash of the invitation token is stored.
    op.execute("""
        CREATE TABLE invitations (
            id           uuid PRIMARY KEY,
            tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email        text NOT NULL,
            role         text NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
            token_hash   text NOT NULL UNIQUE,
            invited_by   uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            expires_at   timestamptz NOT NULL,
            accepted_at  timestamptz,
            revoked_at   timestamptz
        )
    """)
    op.execute("CREATE INDEX invitations_tenant ON invitations (tenant_id, created_at DESC)")
    # Append-only: the app never updates or deletes rows except the yearly
    # retention purge. actor_email is kept so entries survive a user's removal.
    op.execute("""
        CREATE TABLE audit_events (
            id             bigserial PRIMARY KEY,
            tenant_id      uuid,
            actor_user_id  uuid,
            actor_email    text,
            action         text NOT NULL,
            target_type    text,
            target_id      text,
            details        jsonb NOT NULL DEFAULT '{}'::jsonb,
            ip             text,
            user_agent     text,
            request_id     text,
            at             timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX audit_events_tenant ON audit_events (tenant_id, at DESC)")
    # One OIDC identity provider per account (Okta, Microsoft Entra, Auth0…).
    # The client secret is encrypted with the app's secrets key.
    op.execute("""
        CREATE TABLE tenant_sso (
            tenant_id         uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            issuer            text NOT NULL,
            client_id         text NOT NULL,
            client_secret_enc text,
            allowed_domains   text[] NOT NULL DEFAULT '{}',
            default_role      text NOT NULL DEFAULT 'viewer'
                              CHECK (default_role IN ('admin', 'editor', 'viewer')),
            require_sso       boolean NOT NULL DEFAULT false,
            enabled           boolean NOT NULL DEFAULT true,
            updated_at        timestamptz NOT NULL DEFAULT now()
        )
    """)
    # A started SSO sign-in: single use, short-lived (state, nonce, PKCE).
    op.execute("""
        CREATE TABLE sso_logins (
            state          text PRIMARY KEY,
            nonce          text NOT NULL,
            code_verifier  text NOT NULL,
            provider       text NOT NULL,
            tenant_id      uuid,
            created_at     timestamptz NOT NULL DEFAULT now()
        )
    """)

    # Existing accounts: their login becomes the Owner.
    op.execute("""
        INSERT INTO users (id, email, name, password_hash, created_at)
        SELECT id, email, name, password_hash, created_at FROM tenants
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO memberships (user_id, tenant_id, role, created_at)
        SELECT id, id, 'owner', created_at FROM tenants
        ON CONFLICT DO NOTHING
    """)
    # The account keeps its contact email; passwords now live on users.
    op.execute("ALTER TABLE tenants ALTER COLUMN password_hash DROP NOT NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sso_logins")
    op.execute("DROP TABLE IF EXISTS tenant_sso")
    op.execute("DROP TABLE IF EXISTS audit_events")
    op.execute("DROP TABLE IF EXISTS invitations")
    op.execute("DROP TABLE IF EXISTS memberships")
    op.execute("DROP TABLE IF EXISTS users")
