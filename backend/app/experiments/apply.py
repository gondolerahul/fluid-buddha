"""
What a new conversation starts with (M2-4): the visitor's test variant when
they are in one, else the site's defaults from the agent profile.

The widget says which variant it is in (``exp = {"id", "arm"}``); the server
only ever looks that up among the running test's own variants, so a client
can pick between texts the site owner wrote but never supply its own.
"""
from __future__ import annotations

from typing import Any, Optional

from app.db import session_scope
from app.experiments import store as exp_store
from app.orchestrator.profile import profile_for


async def session_settings(site_key: str, exp: Any) -> dict:
    """``{greeting, persona, tour}`` for a new conversation. ``greeting`` and
    ``persona`` are None when the site has none (the model writes a
    page-aware welcome; the persona is read from the conversation)."""
    overrides: dict = {}
    if isinstance(exp, dict) and exp.get("id") and exp.get("arm"):
        try:
            async with session_scope() as db:
                overrides = await exp_store.overrides_for(db, site_key, exp["id"], exp["arm"])
        except Exception:  # never let a test lookup stop a conversation
            overrides = {}
    profile = profile_for(site_key)
    persona: Optional[str] = overrides.get("persona", profile.default_persona) or None
    if persona not in profile.persona_slugs:
        persona = None
    return {
        "greeting": overrides.get("greeting") or profile.greeting or None,
        "persona": persona,
        "tour": bool(overrides.get("tour", profile.tour_enabled)),
    }
