"""
Live state in Postgres (M2-2): presence, takeovers, the people's messages.

The bus (``bus.py``) moves events; these tables are what a console loads when
it opens, what survives a replica restart, and what goes in the transcript.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# A session is live while seen within this window (the voice socket beats
# every HEARTBEAT_S; a text visitor counts as live for a while after a turn).
LIVE_WINDOW_S = 120
HEARTBEAT_S = 30


@dataclass
class Takeover:
    id: uuid.UUID
    operator_user_id: Optional[uuid.UUID]
    operator_name: str
    started_at: datetime

    def public(self) -> dict:
        return {"id": str(self.id), "operator_user_id": str(self.operator_user_id)
                if self.operator_user_id else None, "operator_name": self.operator_name,
                "started_at": self.started_at.isoformat()}


# ---- presence --------------------------------------------------------------------

async def seen(db: AsyncSession, site_key: str, session_id: str, channel: str, *,
               persona: Optional[str] = None, page: Optional[str] = None) -> None:
    await db.execute(text(
        "INSERT INTO live_presence (site_key, session_id, channel, persona, page) "
        "VALUES (:s, :sid, :ch, :p, :pg) ON CONFLICT (site_key, session_id) DO UPDATE SET "
        "last_seen = now(), persona = COALESCE(EXCLUDED.persona, live_presence.persona), "
        "page = COALESCE(EXCLUDED.page, live_presence.page)"),
        {"s": site_key, "sid": session_id, "ch": channel, "p": persona, "pg": page})


async def gone(db: AsyncSession, site_key: str, session_id: str) -> None:
    await db.execute(text("DELETE FROM live_presence WHERE site_key = :s AND session_id = :sid"),
                     {"s": site_key, "sid": session_id})


async def sweep(db: AsyncSession) -> int:
    n = (await db.execute(text(
        "DELETE FROM live_presence WHERE last_seen < now() - make_interval(secs => :w * 3)"),
        {"w": LIVE_WINDOW_S})).rowcount
    await db.commit()
    return n or 0


async def live_sessions(db: AsyncSession, site_keys: list[str]) -> list[dict]:
    """Live visitors on these sites, newest activity first, with what the
    console needs to triage: last question, lead score, takeover."""
    if not site_keys:
        return []
    rows = (await db.execute(text("""
        SELECT p.site_key, p.session_id, p.channel, p.persona, p.page, p.started_at,
               p.last_seen, c.id AS conversation_id, COALESCE(c.turns, 0) AS turns,
               (SELECT question FROM conversation_turns t WHERE t.conversation_id = c.id
                ORDER BY t.created_at DESC LIMIT 1) AS last_question,
               (SELECT max(score) FROM leads l WHERE l.conversation_id = c.id) AS lead_score,
               (SELECT hot_lead_score FROM site_integrations i WHERE i.site_key = p.site_key)
                 AS hot_score,
               k.id AS takeover_id, k.operator_name, k.operator_user_id,
               k.started_at AS takeover_at
        FROM live_presence p
        LEFT JOIN conversations c ON c.site_key = p.site_key AND c.session_id = p.session_id
        LEFT JOIN live_takeovers k ON k.site_key = p.site_key AND k.session_id = p.session_id
             AND k.ended_at IS NULL
        WHERE p.site_key = ANY(:keys)
          AND p.last_seen > now() - make_interval(secs => :w)
        ORDER BY p.last_seen DESC LIMIT 200
    """), {"keys": site_keys, "w": LIVE_WINDOW_S})).mappings().all()
    out = []
    for r in rows:
        hot_at = r["hot_score"] if r["hot_score"] is not None else 60
        out.append({
            "site_key": r["site_key"], "session_id": r["session_id"], "channel": r["channel"],
            "persona": r["persona"], "page": r["page"],
            "started_at": r["started_at"].isoformat(), "last_seen": r["last_seen"].isoformat(),
            "conversation_id": str(r["conversation_id"]) if r["conversation_id"] else None,
            "turns": r["turns"], "last_question": r["last_question"],
            "lead_score": r["lead_score"],
            "hot": r["lead_score"] is not None and r["lead_score"] >= hot_at,
            "takeover": {"id": str(r["takeover_id"]), "operator_name": r["operator_name"],
                         "operator_user_id": str(r["operator_user_id"])
                         if r["operator_user_id"] else None,
                         "started_at": r["takeover_at"].isoformat()}
            if r["takeover_id"] else None,
        })
    return out


async def is_live(db: AsyncSession, site_key: str, session_id: str) -> bool:
    return bool((await db.execute(text(
        "SELECT 1 FROM live_presence WHERE site_key = :s AND session_id = :sid "
        "AND last_seen > now() - make_interval(secs => :w)"),
        {"s": site_key, "sid": session_id, "w": LIVE_WINDOW_S})).first())


# ---- takeovers --------------------------------------------------------------------

async def active(db: AsyncSession, site_key: str, session_id: str) -> Optional[Takeover]:
    r = (await db.execute(text(
        "SELECT id, operator_user_id, operator_name, started_at FROM live_takeovers "
        "WHERE site_key = :s AND session_id = :sid AND ended_at IS NULL"),
        {"s": site_key, "sid": session_id})).mappings().first()
    return Takeover(**r) if r else None


async def start(db: AsyncSession, site_key: str, session_id: str, *,
                operator_user_id: uuid.UUID, operator_name: str) -> Optional[Takeover]:
    """Take over, unless someone already has (then None)."""
    tid = uuid.uuid4()
    r = (await db.execute(text(
        "INSERT INTO live_takeovers (id, site_key, session_id, operator_user_id, operator_name) "
        "VALUES (:id, :s, :sid, :u, :n) ON CONFLICT DO NOTHING "
        "RETURNING id, operator_user_id, operator_name, started_at"),
        {"id": tid, "s": site_key, "sid": session_id, "u": operator_user_id,
         "n": operator_name})).mappings().first()
    return Takeover(**r) if r else None


async def end(db: AsyncSession, site_key: str, session_id: str) -> Optional[Takeover]:
    r = (await db.execute(text(
        "UPDATE live_takeovers SET ended_at = now() WHERE site_key = :s AND session_id = :sid "
        "AND ended_at IS NULL RETURNING id, operator_user_id, operator_name, started_at"),
        {"s": site_key, "sid": session_id})).mappings().first()
    return Takeover(**r) if r else None


# ---- messages ---------------------------------------------------------------------

async def add_message(db: AsyncSession, site_key: str, session_id: str, sender: str,
                      text_: str, author: Optional[str] = None) -> dict:
    r = (await db.execute(text(
        "INSERT INTO live_messages (site_key, session_id, sender, author, text) "
        "VALUES (:s, :sid, :snd, :a, :t) RETURNING id, at"),
        {"s": site_key, "sid": session_id, "snd": sender, "a": author,
         "t": text_[:4000]})).mappings().one()
    return {"id": r["id"], "sender": sender, "author": author, "text": text_[:4000],
            "at": r["at"].isoformat()}


async def messages(db: AsyncSession, site_key: str, session_id: str) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, sender, author, text, at FROM live_messages WHERE site_key = :s "
        "AND session_id = :sid ORDER BY id"), {"s": site_key, "sid": session_id})).mappings().all()
    return [{**dict(r), "at": r["at"].isoformat()} for r in rows]
