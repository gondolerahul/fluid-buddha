"""In-memory conversation registry shared by the HTTP and WebSocket paths.

A real deployment would back this with Redis; for the framework's scope (a
handful of internal sites) an in-process dict is sufficient and keeps the
sliding-window context warm across turns within a session.
"""
from __future__ import annotations

import uuid

from app.orchestrator.state import ConversationState


class SessionStore:
    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}

    def get_or_create(
        self, session_id: str | None, *, site_key: str = "hirebuddha"
    ) -> tuple[str, ConversationState]:
        sid = session_id or uuid.uuid4().hex
        state = self._states.get(sid)
        if state is None:
            state = ConversationState(site_key=site_key)
            self._states[sid] = state
        return sid, state

    def drop(self, session_id: str) -> None:
        self._states.pop(session_id, None)


store = SessionStore()
