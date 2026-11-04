"""
Conversation store + Insights queries (WS10).

Every answered visitor question (voice or text, fresh or replayed) appends one
``conversation_turns`` row to its session's ``conversations`` row. On top of
that the console gets: a transcript viewer, the most-asked questions, the
knowledge gaps (questions the agent could not ground in the site's content —
each one a source worth adding), and the visitor → engaged funnel.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cortex.episodic import normalize_question

logger = logging.getLogger(__name__)

# A conversation with at least this many questions counts as "engaged".
ENGAGED_TURNS = 2
# Small talk ("hi") is ungrounded by nature, not a gap in the content, so it
# never counts as unanswered.
SMALL_TALK = "greeting"


async def record_turn(
    db: AsyncSession, *, site_key: str, session_id: str, channel: str,
    question: str, answer: str, intent: Optional[str] = None,
    persona: Optional[str] = None, page: Optional[str] = None,
    grounding: Optional[dict] = None, served_from_cache: bool = False,
    consent_at: Optional[datetime] = None, components: Optional[list] = None,
) -> None:
    """Append one turn to the session's conversation (created on first turn).
    ``consent_at`` is when the visitor allowed the microphone (WS8). The caller
    owns the transaction."""
    if not (question or "").strip():
        return
    g = grounding or {}
    found = bool(g.get("found"))
    unanswered = not found and intent != SMALL_TALK
    conv_id = (await db.execute(text(
        "INSERT INTO conversations "
        "(id, site_key, session_id, channel, persona, first_page, turns, ungrounded, "
        " consent_at) VALUES (:id, :s, :sid, :ch, :p, :pg, 1, :ug, :ca) "
        "ON CONFLICT (site_key, session_id) DO UPDATE SET "
        "turns = conversations.turns + 1, "
        "ungrounded = conversations.ungrounded + EXCLUDED.ungrounded, "
        "persona = COALESCE(EXCLUDED.persona, conversations.persona), "
        "consent_at = COALESCE(conversations.consent_at, EXCLUDED.consent_at), "
        "last_at = now() "
        "RETURNING id"
    ), {
        "id": uuid.uuid4(), "s": site_key, "sid": session_id, "ch": channel,
        "p": persona, "pg": page, "ug": 1 if unanswered else 0, "ca": consent_at,
    })).scalar_one()
    await db.execute(text(
        "INSERT INTO conversation_turns "
        "(id, conversation_id, site_key, question, q_norm, answer, intent, persona, "
        " page, found, confidence, sources, served_from_cache, components) VALUES "
        "(:id, :c, :s, :q, :qn, :a, :i, :p, :pg, :f, :conf, CAST(:src AS jsonb), :cached, "
        " CAST(:comp AS jsonb))"
    ), {
        "id": uuid.uuid4(), "c": conv_id, "s": site_key, "q": question[:2000],
        "qn": normalize_question(question), "a": answer or "", "i": intent,
        "p": persona, "pg": page, "f": found,
        "conf": float(g.get("confidence") or 0.0),
        "src": json.dumps(g.get("sources") or []), "cached": served_from_cache,
        # The components shown (their specs), so a recap can draw them again (M2-6).
        "comp": json.dumps(list(components or [])[:6], default=str),
    })


async def summary(db: AsyncSession, site_key: str, days: int = 30) -> dict[str, Any]:
    """Headline numbers, top questions, knowledge gaps and the funnel."""
    params = {"s": site_key, "d": days, "eng": ENGAGED_TURNS}
    since = "now() - make_interval(days => :d)"
    params["talk"] = SMALL_TALK
    head = (await db.execute(text(
        "SELECT count(*) AS conversations, "
        "count(*) FILTER (WHERE turns >= :eng) AS engaged, "
        "coalesce(sum(turns), 0) AS turns "
        f"FROM conversations WHERE site_key = :s AND started_at >= {since}"
    ), params)).mappings().one()
    # Share of real questions (not small talk) answered from the site's content.
    asked = (await db.execute(text(
        "SELECT count(*) FILTER (WHERE coalesce(intent, '') <> :talk) AS asked, "
        "count(*) FILTER (WHERE found) AS grounded FROM conversation_turns "
        f"WHERE site_key = :s AND created_at >= {since}"
    ), params)).mappings().one()

    def grouped(where: str, having: str, limit: int) -> str:
        return (
            "SELECT (array_agg(question ORDER BY created_at DESC))[1] AS question, "
            "q_norm, count(*) AS count, max(created_at) AS last_asked, "
            "max(confidence) AS best_confidence "
            f"FROM conversation_turns WHERE site_key = :s AND created_at >= {since} {where} "
            f"GROUP BY q_norm {having} "
            f"ORDER BY count(*) DESC, max(created_at) DESC LIMIT {limit}"
        )

    top = (await db.execute(text(grouped("", "", 10)), params)).mappings().all()
    # A gap closes once the latest time it was asked got a grounded answer
    # (e.g. after the tenant answered it from this page).
    gaps = (await db.execute(text(grouped(
        "AND coalesce(intent, '') <> :talk",
        "HAVING NOT (array_agg(found ORDER BY created_at DESC))[1]", 20)), params)).mappings().all()

    n_asked, n_grounded = int(asked["asked"]), int(asked["grounded"])
    n_leads = (await db.execute(text(
        f"SELECT count(*) FROM leads WHERE site_key = :s AND created_at >= {since}"
    ), params)).scalar() or 0
    return {
        "days": days,
        "conversations": int(head["conversations"]),
        "engaged": int(head["engaged"]),
        "turns": int(head["turns"]),
        "grounded_rate": round(min(n_grounded, n_asked) / n_asked, 4) if n_asked else None,
        "top_questions": [_question_row(r) for r in top],
        "gaps": [_question_row(r) for r in gaps],
        "funnel": [
            {"stage": "visitors", "label": "Started a conversation",
             "count": int(head["conversations"])},
            {"stage": "engaged", "label": f"Asked {ENGAGED_TURNS}+ questions",
             "count": int(head["engaged"])},
            {"stage": "leads", "label": "Left their details", "count": int(n_leads)},
        ],
    }


def _question_row(r: Any) -> dict[str, Any]:
    return {
        "question": r["question"], "count": int(r["count"]),
        "last_asked": r["last_asked"].isoformat() if r["last_asked"] else None,
        "best_confidence": round(float(r["best_confidence"] or 0.0), 4),
    }


async def list_conversations(
    db: AsyncSession, site_key: str, *, limit: int = 25, offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    total = (await db.execute(text(
        "SELECT count(*) FROM conversations WHERE site_key = :s"), {"s": site_key})).scalar() or 0
    rows = (await db.execute(text(
        "SELECT c.id, c.channel, c.persona, c.first_page, c.turns, c.ungrounded, "
        "c.started_at, c.last_at, "
        "(SELECT question FROM conversation_turns t WHERE t.conversation_id = c.id "
        " ORDER BY t.created_at LIMIT 1) AS first_question "
        "FROM conversations c WHERE c.site_key = :s "
        "ORDER BY c.last_at DESC LIMIT :lim OFFSET :off"
    ), {"s": site_key, "lim": limit, "off": offset})).mappings().all()
    return [_conversation_row(r) for r in rows], int(total)


async def get_conversation(
    db: AsyncSession, site_key: str, conversation_id: uuid.UUID,
) -> Optional[dict[str, Any]]:
    conv = (await db.execute(text(
        "SELECT id, channel, persona, first_page, turns, ungrounded, started_at, last_at, "
        "NULL AS first_question FROM conversations WHERE id = :id AND site_key = :s"
    ), {"id": conversation_id, "s": site_key})).mappings().first()
    if conv is None:
        return None
    turns = (await db.execute(text(
        "SELECT question, answer, intent, persona, page, found, confidence, sources, "
        "served_from_cache, created_at FROM conversation_turns "
        "WHERE conversation_id = :id ORDER BY created_at"
    ), {"id": conversation_id})).mappings().all()
    return {**_conversation_row(conv), "transcript": [
        {
            "question": t["question"], "answer": t["answer"], "intent": t["intent"],
            "persona": t["persona"], "page": t["page"], "found": t["found"],
            "confidence": round(float(t["confidence"] or 0.0), 4),
            "sources": t["sources"] if isinstance(t["sources"], list) else [],
            "served_from_cache": t["served_from_cache"],
            "unanswered": not t["found"] and t["intent"] != SMALL_TALK,
            "at": t["created_at"].isoformat(),
        } for t in turns
    ]}


def _conversation_row(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]), "channel": r["channel"], "persona": r["persona"],
        "first_page": r["first_page"], "turns": r["turns"], "ungrounded": r["ungrounded"],
        "first_question": r["first_question"],
        "started_at": r["started_at"].isoformat(), "last_at": r["last_at"].isoformat(),
    }


# ---- Insights v2 (M2-5): what visitors' questions say about the deal ---------------

_STOP = frozenset(
    "a an and are be can could do does for from have how i if in is it its me my of on or "
    "our please should so that the this to we what when where which will with would you your "
    "support supports add any plan plans there feature".split())


def _words(text_: str) -> frozenset[str]:
    import re
    return frozenset(w for w in re.findall(r"[a-z0-9]+", (text_ or "").lower())
                     if w not in _STOP and len(w) > 1)


def group_requests(items: list[dict[str, Any]], threshold: float = 0.5) -> list[dict[str, Any]]:
    """Feature requests that say the same thing, grouped: greedy, by word
    overlap (Jaccard) with each group's first request. ``items`` newest
    first; each group keeps its newest wording and up to 3 examples."""
    groups: list[dict[str, Any]] = []
    for it in items:
        words = _words(it["text"])
        best, best_score = None, 0.0
        for g in groups:
            union = words | g["_words"]
            score = len(words & g["_words"]) / len(union) if union else 0.0
            if score > best_score:
                best, best_score = g, score
        if best is not None and best_score >= threshold:
            best["count"] += 1
            if len(best["examples"]) < 3:
                best["examples"].append(it)
        else:
            groups.append({"text": it["text"], "count": 1, "last_at": it["at"],
                           "examples": [it], "_words": words})
    for g in groups:
        g.pop("_words")
    return sorted(groups, key=lambda g: -g["count"])   # stable: newest first among ties


async def signals(db: AsyncSession, site_key: str, days: int = 30) -> dict[str, Any]:
    """Objections by type (with the previous period for a trend), competitor
    mentions, grouped feature requests and buying signals, with example
    questions linked to their conversations."""
    from app.insights.classify import OBJECTION_LABELS, OBJECTION_TYPES

    p = {"s": site_key, "d": days}
    cur = "t.created_at >= now() - make_interval(days => :d)"
    prev = ("t.created_at < now() - make_interval(days => :d) "
            "AND t.created_at >= now() - make_interval(days => :d * 2)")

    async def counts(column: str, window: str) -> dict[str, int]:
        rows = (await db.execute(text(
            f"SELECT x AS k, count(*) AS n FROM conversation_turns t, unnest(t.{column}) AS x "
            f"WHERE t.site_key = :s AND {window} GROUP BY x"), p)).mappings().all()
        return {r["k"]: int(r["n"]) for r in rows}

    async def examples(column: str) -> dict[str, list[dict]]:
        rows = (await db.execute(text(
            f"SELECT x AS k, t.question, t.created_at, t.conversation_id FROM conversation_turns t, "
            f"unnest(t.{column}) AS x WHERE t.site_key = :s AND {cur} "
            "ORDER BY t.created_at DESC LIMIT 400"), p)).mappings().all()
        out: dict[str, list[dict]] = {}
        for r in rows:
            lst = out.setdefault(r["k"], [])
            if len(lst) < 3:
                lst.append(_example(r))
        return out

    ob_now, ob_prev, ob_ex = await counts("objections", cur), await counts("objections", prev), \
        await examples("objections")
    co_now, co_prev, co_ex = await counts("competitors", cur), await counts("competitors", prev), \
        await examples("competitors")

    req_rows = (await db.execute(text(
        "SELECT t.feature_request AS text, t.question, t.created_at, t.conversation_id "
        f"FROM conversation_turns t WHERE t.site_key = :s AND {cur} "
        "AND t.feature_request IS NOT NULL ORDER BY t.created_at DESC LIMIT 500"), p)).mappings().all()
    requests = group_requests([{**_example(r), "text": r["text"]} for r in req_rows])

    head = (await db.execute(text(
        "SELECT count(*) FILTER (WHERE classified_at IS NOT NULL) AS classified, "
        "count(*) FILTER (WHERE classified_at IS NULL) AS pending, "
        "count(*) FILTER (WHERE buying_signal) AS buying, "
        "count(DISTINCT conversation_id) FILTER (WHERE buying_signal) AS buying_conversations "
        f"FROM conversation_turns t WHERE t.site_key = :s AND {cur}"), p)).mappings().one()
    return {
        "days": days,
        "classified": int(head["classified"]), "pending": int(head["pending"]),
        "objections": [
            {"type": t, "label": OBJECTION_LABELS[t], "count": ob_now.get(t, 0),
             "previous": ob_prev.get(t, 0), "examples": ob_ex.get(t, [])}
            for t in sorted(OBJECTION_TYPES, key=lambda t: -ob_now.get(t, 0)) if ob_now.get(t) or ob_prev.get(t)
        ],
        "competitors": [
            {"name": n, "count": c, "previous": co_prev.get(n, 0), "examples": co_ex.get(n, [])}
            for n, c in sorted(co_now.items(), key=lambda kv: -kv[1])
        ],
        "requests": requests[:30],
        "buying_signals": {"turns": int(head["buying"]),
                           "conversations": int(head["buying_conversations"])},
    }


def _example(r: Any) -> dict[str, Any]:
    return {"question": r["question"], "at": r["created_at"].isoformat(),
            "conversation_id": str(r["conversation_id"])}
