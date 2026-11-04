"""A plan change scheduled for the next renewal (WS12): the replacement
Razorpay subscription, used when the current one can't be changed in place
(UPI Autopay).

Revision ID: 0011_next_subscription
Revises: 0010_overage_links
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0011_next_subscription"
down_revision = "0010_overage_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # next_status mirrors Razorpay: created (mandate not approved yet) →
    # authenticated (approved, starts at the renewal) → active (handed over).
    op.execute("""
        ALTER TABLE tenant_billing
            ADD COLUMN next_subscription_id text UNIQUE,
            ADD COLUMN next_plan text,
            ADD COLUMN next_status text
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_billing
            DROP COLUMN IF EXISTS next_status, DROP COLUMN IF EXISTS next_plan,
            DROP COLUMN IF EXISTS next_subscription_id
    """)
