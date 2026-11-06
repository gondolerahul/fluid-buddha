"""Security controls (M2-11).

``user_sessions``: one row per sign-in, so a session can time out when idle,
end at an absolute limit, and be revoked (sign out, sign out everywhere, a
password change, removal from the team). Tokens carry the session id.

``users`` gains TOTP two-factor fields (secret encrypted, last used time step
against replay, hashed recovery codes) and lockout counters for repeated wrong
passwords or codes. ``tenants.require_mfa`` makes two-factor mandatory for the
account's password sign-ins.

The lead webhook signing secret and the Slack webhook URL (which is itself a
credential) were stored as plain text; they are encrypted here and from now on.

Revision ID: 0024_security
Revises: 0023_actions
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0024_security"
down_revision = "0023_actions"
branch_labels = None
depends_on = None

_ENCRYPTED = ("webhook_secret", "slack_webhook_url")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE user_sessions (
            id            uuid PRIMARY KEY,
            user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            method        text NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now(),
            last_seen_at  timestamptz NOT NULL DEFAULT now(),
            expires_at    timestamptz NOT NULL,
            revoked_at    timestamptz,
            ip            text,
            user_agent    text
        )
    """)
    op.execute("CREATE INDEX user_sessions_user ON user_sessions (user_id, created_at DESC)")
    op.execute("""
        ALTER TABLE users
            ADD COLUMN totp_secret_enc     text,
            ADD COLUMN totp_pending_enc    text,
            ADD COLUMN totp_enabled_at     timestamptz,
            ADD COLUMN totp_last_step      bigint,
            ADD COLUMN recovery_codes      jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN failed_attempts     integer NOT NULL DEFAULT 0,
            ADD COLUMN locked_until        timestamptz,
            ADD COLUMN password_changed_at timestamptz
    """)
    op.execute("ALTER TABLE tenants ADD COLUMN require_mfa boolean NOT NULL DEFAULT false")

    from app.security.secrets import encrypt

    conn = op.get_bind()
    rows = conn.execute(text(
        "SELECT site_key, webhook_secret, slack_webhook_url FROM site_integrations")).mappings().all()
    for row in rows:
        values = {c: encrypt(row[c]) if row[c] and not str(row[c]).startswith("gAAAAA") else row[c]
                  for c in _ENCRYPTED}
        conn.execute(text(
            "UPDATE site_integrations SET webhook_secret = :webhook_secret, "
            "slack_webhook_url = :slack_webhook_url WHERE site_key = :s"),
            {**values, "s": row["site_key"]})


def downgrade() -> None:
    from app.security.secrets import decrypt

    conn = op.get_bind()
    rows = conn.execute(text(
        "SELECT site_key, webhook_secret, slack_webhook_url FROM site_integrations")).mappings().all()
    for row in rows:
        values = {c: decrypt(row[c]) if row[c] and str(row[c]).startswith("gAAAAA") else row[c]
                  for c in _ENCRYPTED}
        conn.execute(text(
            "UPDATE site_integrations SET webhook_secret = :webhook_secret, "
            "slack_webhook_url = :slack_webhook_url WHERE site_key = :s"),
            {**values, "s": row["site_key"]})
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS require_mfa")
    op.execute("""
        ALTER TABLE users
            DROP COLUMN IF EXISTS totp_secret_enc, DROP COLUMN IF EXISTS totp_pending_enc,
            DROP COLUMN IF EXISTS totp_enabled_at, DROP COLUMN IF EXISTS totp_last_step,
            DROP COLUMN IF EXISTS recovery_codes, DROP COLUMN IF EXISTS failed_attempts,
            DROP COLUMN IF EXISTS locked_until, DROP COLUMN IF EXISTS password_changed_at
    """)
    op.execute("DROP TABLE IF EXISTS user_sessions")
