"""Proactive triggers (M2-3): per-site rules for when the agent speaks up
first, and what visitors did when it did.

Revision ID: 0018_triggers
Revises: 0017_live
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0018_triggers"
down_revision = "0017_live"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # kind: time_on_page {seconds} | scroll_depth {percent} | exit_intent {} |
    #       return_visit {visits, within_days}. pages: path globs ("/pricing*"),
    # empty = every page. action: nudge (a bubble by the launcher) | open.
    op.execute("""
        CREATE TABLE trigger_rules (
            id           uuid PRIMARY KEY,
            site_key     text NOT NULL,
            name         text NOT NULL,
            enabled      boolean NOT NULL DEFAULT true,
            kind         text NOT NULL CHECK (kind IN ('time_on_page', 'scroll_depth',
                                                       'exit_intent', 'return_visit')),
            params       jsonb NOT NULL DEFAULT '{}'::jsonb,
            pages        text[] NOT NULL DEFAULT '{}',
            message      text NOT NULL,
            action       text NOT NULL DEFAULT 'nudge' CHECK (action IN ('nudge', 'open')),
            max_per_day  integer NOT NULL DEFAULT 1 CHECK (max_per_day BETWEEN 1 AND 10),
            priority     integer NOT NULL DEFAULT 50,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX trigger_rules_site ON trigger_rules (site_key)")
    # visitor_id is the widget's anonymous id (the one experiments use).
    op.execute("""
        CREATE TABLE trigger_events (
            id          bigserial PRIMARY KEY,
            site_key    text NOT NULL,
            rule_id     uuid NOT NULL REFERENCES trigger_rules(id) ON DELETE CASCADE,
            visitor_id  text NOT NULL,
            event       text NOT NULL CHECK (event IN ('shown', 'clicked', 'dismissed', 'engaged')),
            page        text,
            at          timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX trigger_events_rule ON trigger_events (rule_id, at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trigger_events")
    op.execute("DROP TABLE IF EXISTS trigger_rules")
