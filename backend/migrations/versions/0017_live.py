"""Live takeover (M2-2): who is on the site right now, which conversations a
person has taken over from the agent, and what the people said.

Revision ID: 0017_live
Revises: 0016_sso_domains
Create Date: 2026-11-04
"""
from __future__ import annotations

from alembic import op

revision = "0017_live"
down_revision = "0016_sso_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per visitor session with the widget open. last_seen is refreshed
    # by the voice socket's heartbeat and by each text turn; a row older than
    # the live window simply isn't live any more (and is swept).
    op.execute("""
        CREATE TABLE live_presence (
            site_key    text NOT NULL,
            session_id  text NOT NULL,
            channel     text NOT NULL CHECK (channel IN ('voice', 'text')),
            persona     text,
            page        text,
            started_at  timestamptz NOT NULL DEFAULT now(),
            last_seen   timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (site_key, session_id)
        )
    """)
    op.execute("CREATE INDEX live_presence_seen ON live_presence (site_key, last_seen DESC)")
    # A takeover is active while ended_at is NULL; at most one per session.
    op.execute("""
        CREATE TABLE live_takeovers (
            id                uuid PRIMARY KEY,
            site_key          text NOT NULL,
            session_id        text NOT NULL,
            operator_user_id  uuid,
            operator_name     text NOT NULL,
            started_at        timestamptz NOT NULL DEFAULT now(),
            ended_at          timestamptz
        )
    """)
    op.execute("CREATE UNIQUE INDEX live_takeovers_active ON live_takeovers "
               "(site_key, session_id) WHERE ended_at IS NULL")
    # What the visitor and the person said during a takeover (and notes such as
    # "voice call ended, 3 min"). Visitor text is stored PII-masked (WS8).
    op.execute("""
        CREATE TABLE live_messages (
            id          bigserial PRIMARY KEY,
            site_key    text NOT NULL,
            session_id  text NOT NULL,
            sender      text NOT NULL CHECK (sender IN ('visitor', 'operator', 'system')),
            author      text,
            text        text NOT NULL,
            at          timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX live_messages_session ON live_messages (site_key, session_id, id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS live_messages")
    op.execute("DROP TABLE IF EXISTS live_takeovers")
    op.execute("DROP TABLE IF EXISTS live_presence")
