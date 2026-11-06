"""
Returning-visitor memory, opt-in (M3-3).

A site offers it (Privacy settings, off by default); a visitor turns it on in
the widget ("Remember me"). From then on their conversations on that site are
linked to their anonymous visitor id, and a background job keeps a short
memory: the topics they asked about, the components they explored, what the
agent couldn't answer, whether they left their details. It is built from the
stored transcript, which is already PII-masked, and never leaves the site.

On their next visit the agent greets them with it ("Welcome back — last time
you asked about SSO and pricing…") and has it in the conversation's history.

"Forget me" (widget, typed or spoken), turning the feature off, visitor
erasure, retention (``memory_days`` after the last visit) and deleting the
site all remove it and unlink their conversations.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

VISITOR_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
FORGET_RE = re.compile(
    r"\b(forget (me|about me|what i (said|asked))|delete my (data|history|conversations?)|"
    r"don'?t remember me)\b|मुझे भूल जाओ|मुझे भूल जाइए|\bmujhe bhool ja",
    re.IGNORECASE)

FORGOT = {"en": "Done — I've forgotten our past conversations. Nothing from today will be remembered either.", "hi": 'हो गया — मैंने हमारी पिछली बातचीत भुला दी है। आज की बातचीत भी याद नहीं रखी जाएगी।'}
NOTHING = {"en": "I don't keep a memory of our conversations here, so there's nothing to forget.", "hi": 'मैं यहाँ हमारी बातचीत याद नहीं रखती, इसलिए भुलाने को कुछ नहीं है।'}


def wants_forget(text_: str) -> bool:
    return bool(FORGET_RE.search(text_ or ""))


_COLS = ("site_key, visitor_id, opted_in_at, summary, topics, components, open_questions, persona, "
         "left_details, conversations, lang, built_at, last_seen_at")


def valid_visitor(v: Any) -> Optional[str]:
    v = str(v or "")
    return v if VISITOR_RE.match(v) else None


async def enabled(db: AsyncSession, site_key: str) -> bool:
    return bool((await db.execute(text(
        "SELECT memory_enabled FROM site_privacy WHERE site_key = :s"), {"s": site_key})).scalar())


async def get(db: AsyncSession, site_key: str, visitor: Optional[str]) -> Optional[dict[str, Any]]:
    """The visitor's memory on this site, if they opted in and the site still offers it."""
    visitor = valid_visitor(visitor)
    if not visitor or not await enabled(db, site_key):
        return None
    row = (await db.execute(text(f"SELECT {_COLS} FROM visitor_memories WHERE site_key = :s AND visitor_id = :v"),
                            {"s": site_key, "v": visitor})).mappings().first()
    return dict(row) if row else None


async def opt_in(db: AsyncSession, site_key: str, visitor: str) -> None:
    await db.execute(text(
        "INSERT INTO visitor_memories (site_key, visitor_id) VALUES (:s, :v) "
        "ON CONFLICT (site_key, visitor_id) DO UPDATE SET last_seen_at = now()"),
        {"s": site_key, "v": visitor})


async def forget(db: AsyncSession, site_key: str, visitor: str) -> bool:
    """Delete the memory and unlink the visitor's conversations on this site."""
    had = (await db.execute(text(
        "DELETE FROM visitor_memories WHERE site_key = :s AND visitor_id = :v"),
        {"s": site_key, "v": visitor})).rowcount
    await db.execute(text(
        "UPDATE conversations SET visitor_id = NULL WHERE site_key = :s AND visitor_id = :v"),
        {"s": site_key, "v": visitor})
    return bool(had)


async def forget_site(db: AsyncSession, site_key: str) -> int:
    """The site stopped offering memory: nothing is kept."""
    n = (await db.execute(text("DELETE FROM visitor_memories WHERE site_key = :s"),
                          {"s": site_key})).rowcount or 0
    await db.execute(text("UPDATE conversations SET visitor_id = NULL WHERE site_key = :s "
                          "AND visitor_id IS NOT NULL"), {"s": site_key})
    return n


async def seen(db: AsyncSession, site_key: str, visitor: str) -> None:
    await db.execute(text(
        "UPDATE visitor_memories SET last_seen_at = now() WHERE site_key = :s AND visitor_id = :v"),
        {"s": site_key, "v": visitor})


def has_content(mem: Optional[dict[str, Any]]) -> bool:
    return bool(mem and (mem.get("topics") or mem.get("components")))


def _join(items: list[str], lang: str) -> str:
    items = [i for i in items if i][:2]
    if len(items) == 2:
        return f"{items[0]} {'और' if lang == 'hi' else 'and'} {items[1]}"
    return items[0] if items else ""


def _quote(topic: str) -> str:
    end = "" if topic.endswith("…") else "?"
    return f"\u201c{topic}{end}\u201d"


def greeting(mem: dict[str, Any], lang: str = "en") -> Optional[str]:
    """The welcome back, from what they explored last time: their latest
    question in their own words, else what they explored."""
    if not has_content(mem):
        return None
    topics = [t for t in mem.get("topics") or [] if t]
    if topics:
        q = _quote(topics[0])
        if lang == "hi":
            return f"फिर से स्वागत है! पिछली बार आपने पूछा था: {q} वहीं से आगे बढ़ें?"
        return f"Welcome back! Last time you asked: {q} Want to pick up where we left off?"
    seen = _join(list(mem.get("components") or []), lang)
    if lang == "hi":
        return f"फिर से स्वागत है! पिछली बार आपने {seen} देखा था। वहीं से आगे बढ़ें?"
    return f"Welcome back! Last time you looked at {seen}. Want to pick up where we left off?"


def note(mem: dict[str, Any]) -> Optional[str]:
    """What the agent is told about the earlier visits."""
    if not has_content(mem):
        return None
    parts = []
    if mem.get("topics"):
        parts.append("they asked about " + "; ".join(mem["topics"][:5]))
    if mem.get("components"):
        parts.append("they explored " + ", ".join(mem["components"][:4]))
    if mem.get("open_questions"):
        parts.append("still open: " + "; ".join(mem["open_questions"][:3]))
    if mem.get("left_details"):
        parts.append("they already left their contact details")
    n = mem.get("conversations") or 1
    return (f"(Notes from this visitor's {n} earlier conversation{'s' if n != 1 else ''}, "
            f"which they asked me to remember: " + "; ".join(parts) + ".)")


# ---- building ------------------------------------------------------------------------

_COMPONENT_NAMES = {
    "roi_calculator": "the ROI calculator", "configurator": "a configurator", "chart": "a chart",
    "table": "a comparison table", "flowchart": "a flowchart", "timeline": "a timeline",
    "scenario_simulator": "a scenario simulator", "tabs": "a side-by-side view",
    "component_diagram": "an architecture diagram", "workflow": "a workflow", "sankey": "a flow diagram",
    "mind_map": "a mind map", "graph": "a graph",
}


def _topic(question: str) -> str:
    q = " ".join((question or "").split()).rstrip("?.! ")
    q = re.sub(r"^(hi|hello|hey|ok|so|and|also|please|can you|could you|tell me)[, ]+", "", q, flags=re.I)
    return q[:70] + ("…" if len(q) > 70 else "")


async def build(db: AsyncSession, site_key: str, visitor: str) -> Optional[dict[str, Any]]:
    """Rebuild the visitor's memory from their linked conversations (newest 3)."""
    convs = (await db.execute(text(
        "SELECT id, persona, last_at FROM conversations WHERE site_key = :s AND visitor_id = :v "
        "ORDER BY last_at DESC LIMIT 3"), {"s": site_key, "v": visitor})).mappings().all()
    if not convs:
        return None
    ids = [c["id"] for c in convs]
    turns = (await db.execute(text(
        "SELECT question, found, components, intent, lang FROM conversation_turns "
        "WHERE conversation_id = ANY(:ids) AND question NOT LIKE '(%' AND coalesce(intent, '') <> 'greeting' "
        "ORDER BY created_at DESC LIMIT 40"), {"ids": ids})).mappings().all()
    topics: list[str] = []
    comps: list[str] = []
    open_q: list[str] = []
    langs: dict[str, int] = {}
    for t in turns:
        topic = _topic(t["question"])
        if topic and topic.lower() not in {x.lower() for x in topics}:
            topics.append(topic)
        if not t["found"] and topic and len(open_q) < 3:
            open_q.append(topic)
        for c in t["components"] or []:
            name = _COMPONENT_NAMES.get((c or {}).get("component_type", ""))
            if name and name not in comps:
                comps.append(name)
        langs[t["lang"] or "en"] = langs.get(t["lang"] or "en", 0) + 1
    left = bool((await db.execute(text(
        "SELECT 1 FROM leads WHERE site_key = :s AND conversation_id = ANY(:ids) LIMIT 1"),
        {"s": site_key, "ids": ids})).first())
    lang = "hi" if langs.get("hi", 0) > langs.get("en", 0) + langs.get("hinglish", 0) else "en"
    persona = next((c["persona"] for c in convs if c["persona"]), None)
    summary = "; ".join(topics[:5])
    total = (await db.execute(text(
        "SELECT count(*) FROM conversations WHERE site_key = :s AND visitor_id = :v"),
        {"s": site_key, "v": visitor})).scalar() or 0
    row = (await db.execute(text(
        "UPDATE visitor_memories SET summary = :sum, topics = :t, components = :c, open_questions = :o, "
        "persona = :p, left_details = :l, conversations = :n, lang = :lang, built_at = now() "
        f"WHERE site_key = :s AND visitor_id = :v RETURNING {_COLS}"),
        {"sum": summary, "t": topics[:8], "c": comps[:6], "o": open_q, "p": persona, "l": left,
         "n": int(total), "lang": lang, "s": site_key, "v": visitor})).mappings().first()
    return dict(row) if row else None


async def build_due(db: AsyncSession, quiet_minutes: int = 10, limit: int = 100) -> int:
    """Memories with a conversation that ended (quiet for ``quiet_minutes``)
    since they were last built."""
    due = (await db.execute(text(
        "SELECT DISTINCT m.site_key, m.visitor_id FROM visitor_memories m "
        "JOIN conversations c ON c.site_key = m.site_key AND c.visitor_id = m.visitor_id "
        "WHERE c.last_at < now() - make_interval(mins => :q) "
        "AND (m.built_at IS NULL OR c.last_at > m.built_at) LIMIT :n"),
        {"q": quiet_minutes, "n": limit})).all()
    for site_key, visitor in due:
        try:
            await build(db, site_key, visitor)
        except Exception as exc:
            logger.warning("memory build failed for %s: %s", site_key, exc)
    await db.commit()
    return len(due)


async def purge_expired(db: AsyncSession) -> int:
    """Memories past the site's ``memory_days`` since the visitor was last seen,
    and every memory on a site that no longer offers it."""
    n = (await db.execute(text(
        "DELETE FROM visitor_memories m USING site_privacy p WHERE p.site_key = m.site_key "
        "AND (NOT p.memory_enabled OR m.last_seen_at < now() - p.memory_days * interval '1 day')"))).rowcount or 0
    n += (await db.execute(text(
        "DELETE FROM visitor_memories m WHERE NOT EXISTS "
        "(SELECT 1 FROM site_privacy p WHERE p.site_key = m.site_key)"))).rowcount or 0
    await db.execute(text(
        "UPDATE conversations c SET visitor_id = NULL WHERE c.visitor_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM visitor_memories m WHERE m.site_key = c.site_key AND m.visitor_id = c.visitor_id)"))
    return n
