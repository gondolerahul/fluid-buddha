"""
Public, read-only widget check.

``GET /widget/config?key=...`` says what a widget key resolves to — the site,
its capability tier and design, and the agent's name — without running an agent
turn (no model or TTS spend, no usage recorded). The console's Install tab uses
it for "Test connection".

Only non-sensitive display settings are returned, so the Origin allow-list is
not applied here: the console checks a key from its own origin, not the
customer's. The turn paths (/chat, /ws/voice) still enforce it.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import session_scope
from app.orchestrator.profile import ensure_profile
from app.tenancy.public_access import PublicAccessError, resolve_public_site

router = APIRouter(tags=["widget"])


@router.get("/widget/config")
async def widget_config(key: str = Query(..., min_length=1, max_length=200)) -> dict:
    try:
        async with session_scope() as db:
            resolved = await resolve_public_site(db, key=key, site=None, intelligence=None)
    except PublicAccessError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    website = resolved.website
    profile = await ensure_profile(resolved.site_key)
    return {
        "site_key": resolved.site_key,
        "intelligence": resolved.intelligence,
        "design": website.design if website else None,
        "accent": website.accent if website else None,
        "agent_name": profile.agent_name,
        "company_name": profile.company_name,
    }
