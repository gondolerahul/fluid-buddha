"""
Conversation state for the HTTP ``/chat`` path, between a visitor's turns.

Two backends behind one interface (F-3):

* **In-process** (default): a dict with an idle timeout and a size cap, so it
  can't grow without bound. Right for a single backend replica.
* **Redis** (``REDIS_URL``): the state is stored as JSON with a sliding TTL, so
  any replica can answer the next turn. Needed to run more than one backend.

A voice WebSocket keeps its state on the connection itself, so it doesn't use
this store.

The state includes the conversation's PII placeholders and their values
(WS8), so a visitor's email typed in turn 1 can still reach ``capture_lead`` in
turn 3. In Redis those expire with the session (``SESSION_TTL_MINUTES``).

A session id is only honoured for the site it was created on: a session from
one site can't be continued on another.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import OrderedDict
from typing import Optional

from app.orchestrator.state import ConversationState

logger = logging.getLogger(__name__)

_PREFIX = "fb:chat:"


class MemorySessionStore:
    def __init__(self, ttl_s: float, max_sessions: int) -> None:
        self.ttl_s = ttl_s
        self.max_sessions = max_sessions
        self._states: OrderedDict[str, tuple[float, ConversationState]] = OrderedDict()

    def _evict(self, now: float) -> None:
        while self._states:
            sid, (seen, _) = next(iter(self._states.items()))
            if now - seen <= self.ttl_s and len(self._states) <= self.max_sessions:
                break
            self._states.pop(sid)

    async def get(self, sid: str) -> Optional[ConversationState]:
        now = time.monotonic()
        self._evict(now)
        hit = self._states.get(sid)
        return hit[1] if hit else None

    async def put(self, sid: str, state: ConversationState) -> None:
        self._states[sid] = (time.monotonic(), state)
        self._states.move_to_end(sid)
        self._evict(time.monotonic())

    async def drop(self, sid: str) -> None:
        self._states.pop(sid, None)


class RedisSessionStore:
    def __init__(self, client, ttl_s: float) -> None:
        self.client = client
        self.ttl_s = int(ttl_s)

    async def get(self, sid: str) -> Optional[ConversationState]:
        raw = await self.client.get(_PREFIX + sid)
        if not raw:
            return None
        try:
            return ConversationState.from_dict(json.loads(raw))
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("unreadable session %s dropped: %s", sid[:8], exc)
            return None

    async def put(self, sid: str, state: ConversationState) -> None:
        await self.client.set(_PREFIX + sid, json.dumps(state.to_dict()), ex=self.ttl_s)

    async def drop(self, sid: str) -> None:
        await self.client.delete(_PREFIX + sid)


class SessionStore:
    """``load`` a visitor's conversation (or start one), ``save`` it after the turn."""

    def __init__(self, backend) -> None:
        self.backend = backend

    async def load(
        self, session_id: Optional[str], *, site_key: str
    ) -> tuple[str, ConversationState]:
        if session_id and len(session_id) <= 64:
            try:
                state = await self.backend.get(session_id)
            except Exception as exc:  # a store outage degrades to a fresh session
                logger.warning("session store unavailable: %s", exc)
                state = None
            if state is not None and state.site_key == site_key:
                return session_id, state
        return uuid.uuid4().hex, ConversationState(site_key=site_key)

    async def save(self, sid: str, state: ConversationState) -> None:
        try:
            await self.backend.put(sid, state)
        except Exception as exc:
            logger.warning("session %s not saved: %s", sid[:8], exc)

    async def drop(self, sid: str) -> None:
        await self.backend.drop(sid)


def build_store() -> SessionStore:
    from app.config import get_settings
    from app.shared_state import redis_client

    settings = get_settings()
    ttl = max(1, settings.session_ttl_minutes) * 60
    client = redis_client()
    if client is not None:
        return SessionStore(RedisSessionStore(client, ttl))
    return SessionStore(MemorySessionStore(ttl, settings.session_cache_max))


store = build_store()
