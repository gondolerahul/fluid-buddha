"""
The visitor's side of live takeover (M2-2), shared by the voice socket
(``app/transport/websocket.py``) and the text path (``app/routes/chat.py``):

* presence — tell operators who's on the site;
* every agent turn is mirrored to the operators watching the site;
* while a person has taken over, the visitor's messages go to them (stored
  masked) instead of to the agent;
* when the agent takes over again, ``catch_up`` folds what was said into its
  history so it doesn't repeat or contradict the person.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.db import session_scope
from app.live import store
from app.live.bus import bus, site_topic
from app.orchestrator.state import ChatMessage, ConversationState

logger = logging.getLogger(__name__)


async def present(site_key: str, session_id: str, channel: str, *, persona: Optional[str] = None,
                  page: Optional[str] = None, announce: bool = False) -> None:
    try:
        async with session_scope() as db:
            await store.seen(db, site_key, session_id, channel, persona=persona, page=page)
        if announce:
            await bus.publish(site_topic(site_key), {
                "type": "visitor_joined", "session_id": session_id, "channel": channel,
                "persona": persona, "page": page})
    except Exception as exc:   # presence is best effort; the conversation goes on
        logger.warning("live presence failed: %s", exc)


async def left(site_key: str, session_id: str) -> None:
    try:
        async with session_scope() as db:
            await store.gone(db, site_key, session_id)
        await bus.publish(site_topic(site_key), {"type": "visitor_left", "session_id": session_id})
    except Exception as exc:
        logger.warning("live presence (leave) failed: %s", exc)


async def taken_over(site_key: str, session_id: str) -> Optional[store.Takeover]:
    try:
        async with session_scope() as db:
            return await store.active(db, site_key, session_id)
    except Exception as exc:   # if in doubt, the agent answers
        logger.warning("takeover check failed: %s", exc)
        return None


async def visitor_said(site_key: str, session_id: str, raw: str, masked: str) -> dict:
    """A visitor message during a takeover: stored masked, shown to the
    operators as typed (they're the site's own team)."""
    async with session_scope() as db:
        msg = await store.add_message(db, site_key, session_id, "visitor", masked)
    await bus.publish(site_topic(site_key), {
        "type": "visitor_message", "session_id": session_id, "message": {**msg, "text": raw}})
    return msg


async def agent_turn(site_key: str, session_id: str, question: str, answer: str) -> None:
    try:
        await bus.publish(site_topic(site_key), {
            "type": "agent_turn", "session_id": session_id, "question": question,
            "answer": answer})
    except Exception as exc:
        logger.debug("live mirror skipped: %s", exc)


async def catch_up(state: ConversationState, site_key: str, session_id: str) -> None:
    """Fold the people's messages since ``state.live_seen`` into the agent's
    history (visitor lines as the user, the person's as the agent's side,
    labelled with their name)."""
    try:
        async with session_scope() as db:
            msgs = [m for m in await store.messages(db, site_key, session_id)
                    if m["id"] > state.live_seen]
    except Exception as exc:
        logger.warning("live catch-up failed: %s", exc)
        return
    for m in msgs:
        if m["sender"] == "visitor":
            state.history.append(ChatMessage(role="user", text=m["text"]))
        elif m["sender"] == "operator":
            state.history.append(ChatMessage(
                role="model", text=f"[{m['author'] or 'A team member'} from the team, in person]: "
                                   f"{m['text']}"))
        state.live_seen = max(state.live_seen, int(m["id"]))
    if len(state.history) > state.max_turns * 2:
        state.history = state.history[-state.max_turns * 2:]
