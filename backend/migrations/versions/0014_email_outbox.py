"""Email outbox (M2-0): every email is queued here and sent by a background
worker with retries, so a slow or failing SMTP server never blocks a request
and nothing is lost across restarts.

Revision ID: 0014_email_outbox
Revises: 0013_cost_alerts
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0014_email_outbox"
down_revision = "0013_cost_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # status: queued → sending → sent | failed (after the last attempt).
    # idem_key: the same logical email (e.g. one weekly digest per account and
    # week) is only ever queued once.
    op.execute("""
        CREATE TABLE email_outbox (
            id               bigserial PRIMARY KEY,
            kind             text NOT NULL,
            tenant_id        uuid,
            to_addr          text NOT NULL,
            subject          text NOT NULL,
            text_body        text NOT NULL,
            html_body        text,
            headers          jsonb NOT NULL DEFAULT '{}'::jsonb,
            idem_key         text UNIQUE,
            status           text NOT NULL DEFAULT 'queued'
                             CHECK (status IN ('queued', 'sending', 'sent', 'failed')),
            attempts         integer NOT NULL DEFAULT 0,
            next_attempt_at  timestamptz NOT NULL DEFAULT now(),
            claimed_at       timestamptz,
            last_error       text,
            created_at       timestamptz NOT NULL DEFAULT now(),
            sent_at          timestamptz
        )
    """)
    op.execute("CREATE INDEX email_outbox_due ON email_outbox (next_attempt_at) "
               "WHERE status = 'queued'")
    op.execute("CREATE INDEX email_outbox_tenant ON email_outbox (tenant_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_outbox")
