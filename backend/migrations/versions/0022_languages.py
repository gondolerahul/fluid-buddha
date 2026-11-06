"""English + Hindi (M2-7).

Cached answers carry the language they were given in, so a Hindi question is
never answered with a replayed English answer (or the other way round). Each
stored conversation turn records the language the visitor wrote in (en, hi,
or hinglish: Hindi in Latin letters), for Insights.

Revision ID: 0022_languages
Revises: 0021_recaps
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

revision = "0022_languages"
down_revision = "0021_recaps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE conversation_cache ADD COLUMN lang text NOT NULL DEFAULT 'en'")
    op.execute("ALTER TABLE conversation_cache ADD CONSTRAINT conversation_cache_lang "
               "CHECK (lang IN ('en', 'hi'))")
    op.execute("ALTER TABLE conversation_turns ADD COLUMN lang text NOT NULL DEFAULT 'en'")
    op.execute("ALTER TABLE conversation_turns ADD CONSTRAINT conversation_turns_lang "
               "CHECK (lang IN ('en', 'hi', 'hinglish'))")


def downgrade() -> None:
    op.execute("ALTER TABLE conversation_turns DROP COLUMN IF EXISTS lang")
    op.execute("ALTER TABLE conversation_cache DROP COLUMN IF EXISTS lang")
