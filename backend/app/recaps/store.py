"""
Shareable recap pages (M2-6): one conversation, summarised, behind a link the
visitor can open on another device or forward to their buying committee.

* A recap is a snapshot of the conversation's turns as stored (questions and
  answers already PII-masked, WS8): the answers, the components shown (their
  specs, re-drawn by the SDK on the page), the cited sources, and next steps
  (the site's call to action, back to the site). Asking again refreshes the
  snapshot and keeps the link.
* The token is 32 random bytes (``secrets.token_urlsafe``): the link is the
  only way in. It stops working after the site's ``recap_days``, and the recap
  goes with its conversation (retention sweep, a visitor's erasure, deleting
  the site).
* Views are counted per viewer (a random cookie id; link-preview bots are not
  counted). Every viewer after the first is a forward. The first view adds 5
  to the conversation's lead score and each forward 10 (capped at 100).
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,64}$")
MAX_TURNS = 30
FIRST_VIEW_POINTS = 5
FORWARD_POINTS = 10


class NothingToRecap(Exception):
    """The session has no conversation with a real question yet."""


def new_token() -> str:
    return secrets.token_urlsafe(32)


async def _turns(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT question, answer, sources, components, page, created_at FROM conversation_turns "
        "WHERE conversation_id = :c AND coalesce(intent, '') <> 'greeting' "
        "AND question NOT LIKE '(%' ORDER BY created_at LIMIT :n"),
        {"c": conversation_id, "n": MAX_TURNS})).mappings().all()
    out = []
    for r in rows:
        sources = r["sources"] if isinstance(r["sources"], list) else json.loads(r["sources"] or "[]")
        comps = r["components"] if isinstance(r["components"], list) else json.loads(r["components"] or "[]")
        out.append({
            "question": r["question"], "answer": r["answer"],
            "sources": [{"label": str(s.get("label") or s.get("document") or "")[:120],
                         "url": s.get("url") if str(s.get("url") or "").startswith("https://") else None}
                        for s in sources if isinstance(s, dict) and (s.get("label") or s.get("document"))][:5],
            "components": [c for c in comps if isinstance(c, dict) and c.get("component_type")][:4],
            "page": r["page"],
        })
    return out


def rule_summary(turns: list[dict[str, Any]]) -> str:
    """A plain summary without a model: what was asked."""
    qs = [t["question"].strip().rstrip("?") for t in turns if t["question"].strip()]
    if not qs:
        return ""
    head = f"You asked {len(qs)} question{'s' if len(qs) != 1 else ''}"
    listed = "; ".join(q[:120] for q in qs[:4])
    more = f", and {len(qs) - 4} more" if len(qs) > 4 else ""
    return f"{head}: {listed}{more}."


SUMMARY_PROMPT = (
    "Summarise this conversation between a website visitor and a company's assistant for the "
    "visitor, in 2-3 plain sentences: what they wanted to know and the key answers. Address the "
    "visitor as 'you'. Don't invent facts. Text like [EMAIL_1] is a hidden detail: leave it out."
)


async def summarize(turns: list[dict[str, Any]], llm: Any = None, model: Optional[str] = None) -> str:
    if llm is None:
        return rule_summary(turns)
    from app.ai.base import ChatMessage

    convo = "\n".join(f"Visitor: {t['question']}\nAssistant: {t['answer'][:600]}" for t in turns[:12])
    try:
        resp = await llm.generate(system=SUMMARY_PROMPT, messages=[ChatMessage(role="user", text=convo)],
                                  model=model, temperature=0.2, max_output_tokens=200, thinking_budget=0)
        text_ = (resp.text or "").strip()
        return text_[:800] if text_ else rule_summary(turns)
    except Exception as exc:
        logger.warning("recap summary failed, using the plain one: %s", exc)
        return rule_summary(turns)


async def create_or_refresh(db: AsyncSession, site_key: str, session_id: str, *,
                            recap_days: int, llm: Any = None, model: Optional[str] = None) -> dict:
    """The session's recap, built (or rebuilt) from its conversation now.
    Raises ``NothingToRecap`` before the visitor has asked anything."""
    conv = (await db.execute(text(
        "SELECT id, first_page FROM conversations WHERE site_key = :s AND session_id = :sid"),
        {"s": site_key, "sid": session_id})).mappings().first()
    if conv is None:
        raise NothingToRecap()
    turns = await _turns(db, conv["id"])
    if not turns:
        raise NothingToRecap()
    content = {"summary": await summarize(turns, llm, model), "turns": turns,
               "first_page": conv["first_page"], "built_at": datetime.now(timezone.utc).isoformat()}
    expires = datetime.now(timezone.utc) + timedelta(days=recap_days)
    row = (await db.execute(text(
        "INSERT INTO recaps (id, token, site_key, conversation_id, content, expires_at) "
        "VALUES (:id, :t, :s, :c, CAST(:content AS jsonb), :exp) "
        "ON CONFLICT (conversation_id) DO UPDATE SET content = EXCLUDED.content, "
        "expires_at = EXCLUDED.expires_at, updated_at = now() "
        "RETURNING id, token, expires_at, conversation_id"),
        {"id": uuid.uuid4(), "t": new_token(), "s": site_key, "c": conv["id"],
         "content": json.dumps(content, default=str), "exp": expires})).mappings().one()
    await db.commit()
    return dict(row)


async def by_token(db: AsyncSession, token: str) -> Optional[dict]:
    """A live (unexpired) recap, or None — the same answer for unknown and expired."""
    if not TOKEN_RE.match(token or ""):
        return None
    row = (await db.execute(text(
        "SELECT id, site_key, conversation_id, content, created_at, updated_at, expires_at "
        "FROM recaps WHERE token = :t AND expires_at > now()"), {"t": token})).mappings().first()
    if row is None:
        return None
    out = dict(row)
    if isinstance(out["content"], str):
        out["content"] = json.loads(out["content"])
    return out


async def record_view(db: AsyncSession, recap: dict, viewer: str) -> dict:
    """Count a view by ``viewer``; a new viewer after the first is a forward.
    Returns ``{"new_viewer", "forward"}``."""
    new = (await db.execute(text(
        "INSERT INTO recap_views (recap_id, viewer) VALUES (:r, :v) "
        "ON CONFLICT (recap_id, viewer) DO UPDATE SET views = recap_views.views + 1, last_at = now() "
        "RETURNING (xmax = 0) AS inserted"), {"r": recap["id"], "v": viewer})).scalar()
    counts = (await db.execute(text(
        "UPDATE recaps SET views = views + 1, viewers = viewers + :n, last_viewed_at = now() "
        "WHERE id = :r RETURNING viewers"), {"r": recap["id"], "n": 1 if new else 0})).scalar()
    forward = bool(new) and counts > 1
    if new:
        await db.execute(text(
            "UPDATE leads SET score = LEAST(100, score + :p) WHERE conversation_id = :c"),
            {"p": FORWARD_POINTS if forward else FIRST_VIEW_POINTS, "c": recap["conversation_id"]})
    await db.commit()
    return {"new_viewer": bool(new), "forward": forward}


async def list_for_site(db: AsyncSession, site_key: str, limit: int = 50) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT r.id, r.token, r.conversation_id, r.created_at, r.updated_at, r.expires_at, r.views, "
        "r.viewers, r.last_viewed_at, r.content->>'summary' AS summary, "
        "(SELECT email FROM leads l WHERE l.conversation_id = r.conversation_id "
        " ORDER BY l.created_at DESC LIMIT 1) AS lead_email "
        "FROM recaps r WHERE r.site_key = :s ORDER BY r.updated_at DESC LIMIT :n"),
        {"s": site_key, "n": limit})).mappings().all()
    return [{
        "id": str(r["id"]), "token": r["token"], "conversation_id": str(r["conversation_id"]),
        "created_at": r["created_at"].isoformat(), "updated_at": r["updated_at"].isoformat(),
        "expires_at": r["expires_at"].isoformat(), "expired": r["expires_at"] < datetime.now(timezone.utc),
        "views": r["views"], "viewers": r["viewers"], "forwards": max(0, r["viewers"] - 1),
        "last_viewed_at": r["last_viewed_at"].isoformat() if r["last_viewed_at"] else None,
        "summary": r["summary"], "lead_email": r["lead_email"],
    } for r in rows]


async def revoke(db: AsyncSession, site_key: str, recap_id: uuid.UUID) -> bool:
    n = (await db.execute(text("DELETE FROM recaps WHERE id = :id AND site_key = :s"),
                          {"id": recap_id, "s": site_key})).rowcount
    await db.commit()
    return bool(n)


async def purge_expired(db: AsyncSession) -> int:
    """Delete expired recaps (they already answer like unknown links)."""
    return (await db.execute(text("DELETE FROM recaps WHERE expires_at < now()"))).rowcount or 0
