"""Overage that Razorpay won't take as an add-on (subscriptions paid by UPI
autopay) is billed with a Razorpay Payment Link instead (WS12).

Revision ID: 0010_overage_links
Revises: 0009_billing
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0010_overage_links"
down_revision = "0009_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pending: not charged yet (retried); addon: on the next subscription
    # invoice; link: payment link sent; paid: link paid; nothing: no overage.
    op.execute("""
        ALTER TABLE billing_overage
            ADD COLUMN status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'addon', 'link', 'paid', 'nothing')),
            ADD COLUMN payment_link_id text,
            ADD COLUMN payment_link_url text,
            ADD COLUMN error text
    """)
    op.execute("UPDATE billing_overage SET status = 'addon' WHERE addon_id IS NOT NULL")
    op.execute("UPDATE billing_overage SET status = 'nothing' WHERE amount = 0")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE billing_overage
            DROP COLUMN IF EXISTS error, DROP COLUMN IF EXISTS payment_link_url,
            DROP COLUMN IF EXISTS payment_link_id, DROP COLUMN IF EXISTS status
    """)
