"""Billing with Razorpay (WS12): each account's plan and subscription, the
Razorpay plans created for the catalog, processed webhooks, and the overage
billed for each period.

Revision ID: 0009_billing
Revises: 0008_ttfa
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0009_billing"
down_revision = "0008_ttfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # status mirrors Razorpay's subscription status; 'none' = never subscribed.
    op.execute("""
        CREATE TABLE tenant_billing (
            tenant_id               uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
            plan                    text NOT NULL DEFAULT 'free',
            pending_plan            text,
            status                  text NOT NULL DEFAULT 'none',
            subscription_id         text UNIQUE,
            current_start           timestamptz,
            current_end             timestamptz,
            cancel_at_cycle_end     boolean NOT NULL DEFAULT false,
            updated_at              timestamptz NOT NULL DEFAULT now()
        )
    """)
    # Razorpay plans are created on first use: one per API key (test and live
    # modes, and different accounts, have separate plans), plan, currency, price.
    op.execute("""
        CREATE TABLE razorpay_plans (
            key_id           text NOT NULL,
            plan             text NOT NULL,
            currency         text NOT NULL,
            amount           integer NOT NULL,
            razorpay_plan_id text NOT NULL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (key_id, plan, currency, amount)
        )
    """)
    # Webhooks are retried by Razorpay: each event is applied once.
    op.execute("""
        CREATE TABLE billing_events (
            event_id     text PRIMARY KEY,
            event        text NOT NULL,
            tenant_id    uuid,
            received_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE billing_overage (
            tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            period_start   timestamptz NOT NULL,
            period_end     timestamptz NOT NULL,
            plan           text NOT NULL,
            conversations  integer NOT NULL,
            extra          integer NOT NULL,
            amount         integer NOT NULL,
            currency       text NOT NULL,
            addon_id       text,
            created_at     timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, period_start)
        )
    """)


def downgrade() -> None:
    for t in ("billing_overage", "billing_events", "razorpay_plans", "tenant_billing"):
        op.execute(f"DROP TABLE IF EXISTS {t}")
