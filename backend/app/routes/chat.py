"""
HTTP text path (the SDR agent without voice).

Wraps the same cognitive loop the WebSocket uses and returns a payload shaped
for the frontend Pragya ``Message`` (text + actions + components + grounding).
This is also the reliable text fallback when the WebSocket drops (Req 4.3).
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from typing import Any

from app.analytics.usage import TurnMetrics, record_turn
from app.db import session_scope
from app.design.system import ensure_design
from app.orchestrator.profile import ensure_profile
from app.orchestrator.rewrite import depends_on_history
from app.orchestrator.state import normalize_sections
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.transport.guard import check_public_budget
from app.transport.session_store import store
from app.trust.pii import PiiVault, contains_pii
from app.trust.settings import get_privacy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _ui_sid() -> str:
    return f"ui_{uuid.uuid4().hex[:10]}"


async def _record_conversation(state, sid: str, question: str, answer: str, intent,
                               grounding, *, served_from_cache: bool, leads=()) -> None:
    """Append the turn to this session's transcript (Insights, WS10; best-effort),
    then save any lead the agent captured in it (WS7)."""
    from app.insights.store import record_turn as record_conversation_turn
    try:
        async with session_scope() as db:
            await record_conversation_turn(
                db, site_key=state.site_key, session_id=sid, channel="text",
                question=question, answer=answer, intent=intent,
                persona=state.persona, page=state.page,
                grounding=grounding, served_from_cache=served_from_cache,
            )
    except Exception as exc:
        logger.warning("conversation record failed: %s", exc)
    if leads:
        from app.leads.capture import save_captured
        await save_captured(state.site_key, sid, state.persona, list(leads))


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    # Widget key (preferred): resolves the site + tier server-side. `site` and
    # `intelligence` are honoured only for built-in demo sites (docs/defects.md D-1).
    key: str | None = None
    site: str = "hirebuddha"
    intelligence: str | None = None  # basic|high|advance|extreme — capability tier
    icp: str | None = None          # current persona reported by the frontend
    page: str | None = None         # current route, for grounding/context
    # scroll targets on the page: ["plans"] or [{"id","label"}]
    sections: list[Any] | None = None


@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> dict:
    rt = request.app.state.runtime
    t0 = time.monotonic()

    # Resolve site + tier server-side so the client can't pick another tenant's
    # knowledge base or escalate its own tier (docs/defects.md D-1).
    try:
        async with session_scope() as rdb:
            resolved = await resolve_public_site(
                rdb, key=req.key, site=req.site, intelligence=req.intelligence,
                origin=request.headers.get("origin"),
            )
            # Per-site rate limit + daily spend cap (docs/defects.md D-3).
            blocked = await check_public_budget(rdb, resolved.site_key, rt.settings)
            privacy = await get_privacy(rdb, resolved.site_key)
    except PublicAccessError as exc:
        raise HTTPException(status_code=403, detail=exc.reason)
    if blocked:
        raise HTTPException(status_code=429, detail=blocked)
    # Load the site's agent profile (name, personas, sitemap) for the prompts.
    await ensure_profile(resolved.site_key)
    await ensure_design(resolved.site_key)  # themes Extreme pages (WS9)

    sid, state = store.get_or_create(req.session_id, site_key=resolved.site_key)
    state.site_key = resolved.site_key
    state.intelligence = resolved.intelligence
    if req.icp:
        state.persona = req.icp
    if req.page:
        state.page = req.page
    if req.sections is not None:
        state.sections = normalize_sections(req.sections)

    # PII masking (WS8): the loop, the history and every store see placeholders.
    # A turn that carries the visitor's details is personal: never replayed or
    # cached.
    pii = state.pii
    pii.enabled = privacy.redact_pii
    message = pii.mask(req.message)
    personal = message != req.message
    # A mid-conversation follow-up is answered fresh and never cached (WS5).
    followup = depends_on_history(message, state.history)

    settings = rt.settings

    # Cache-first (Feature 2): replay a close past answer, or pass near-matches to
    # the loop as context. Runs in its OWN session so a cache hiccup can never
    # poison the main reasoning transaction.
    related: list = []
    replay = None
    if settings.conversation_cache_enabled and not personal and not followup:
        try:
            async with session_scope() as cdb:
                cache = rt.episodic(cdb, state.site_key)
                hits = await cache.query(
                    transcript=message, persona=state.persona,
                    page=state.page, top_k=settings.episodic_top_k,
                )
                # A pinned answer (WS8) replays before the "enough data" gate.
                best = hits[0] if hits else None
                if best and (best.pinned or await cache.count(persona=state.persona)
                             >= settings.episodic_min_episodes):
                    if best.score >= settings.episodic_replay_threshold:
                        replay = best
                        await cache.mark_hit(best.question, state.persona)
                    elif best.score >= settings.episodic_context_threshold:
                        related = hits
        except Exception as exc:
            logger.warning("chat replay check failed: %s", exc)

    if replay is not None:
        state.add_turn(req.message, replay.answer_text)
        try:
            async with session_scope() as adb:
                await record_turn(adb, TurnMetrics(
                    site_key=state.site_key, session_id=sid, channel="text",
                    intent="cached", persona=state.persona, page=state.page,
                    served_from_cache=True,
                    latency_ms=(time.monotonic() - t0) * 1000.0,
                ))
        except Exception as exc:
            logger.debug("usage record (cached) skipped: %s", exc)
        await _record_conversation(state, sid, req.message, replay.answer_text, "cached",
                                   replay.grounding, served_from_cache=True)
        return {
            "text": replay.answer_text, "ack": "", "intent": "cached",
            "persona": state.persona, "actions": replay.actions,
            "components": [{**c, "sync_id": _ui_sid()} for c in replay.components],
            "pages": [], "patches": [],
            # The original answer's sources (WS8); older rows predate storing them.
            "grounding": replay.grounding or {"confidence": 1.0, "found": True, "sources": []},
            "session_id": sid,
        }

    async with session_scope() as db:
        bridge = rt.bridge(db, site_key=state.site_key)
        result = await rt.loop.run_turn(
            user_text=message, state=state, bridge=bridge, related=related,
        )

    # Record the turn for future replay (best-effort, own session).
    # A patch targets this session's components, and a captured lead holds one
    # visitor's contact details, so neither turn may be replayed.
    personal = personal or contains_pii(result.answer_text)
    if (settings.conversation_cache_enabled and result.answer_text
            and not result.patches and not result.leads and not personal
            and not followup):
        try:
            async with session_scope() as db:
                await rt.episodic(db, state.site_key).record(
                    question=message, answer_text=result.answer_text,
                    components=[c.to_dict() for c in result.components],
                    actions=[a.to_dict() for a in result.actions],
                    persona=state.persona, page=state.page, channel="text",
                    grounding=result.grounding.to_dict(),
                )
        except Exception as exc:
            logger.warning("chat record failed: %s", exc)

    # Record cost/performance for this generated turn (best-effort, own session).
    try:
        async with session_scope() as adb:
            metrics = TurnMetrics(
                site_key=state.site_key, session_id=sid, channel="text",
                intent=result.intent, persona=state.persona, page=state.page,
                served_from_cache=False,
                latency_ms=(time.monotonic() - t0) * 1000.0,
            )
            metrics.add_llm(
                kind=result.llm_kind, input_tokens=result.input_tokens,
                output_tokens=result.output_tokens, tool_calls=result.tool_calls,
            )
            await record_turn(adb, metrics)
    except Exception as exc:
        logger.debug("usage record skipped: %s", exc)
    await _record_conversation(state, sid, pii.stored(message),
                               pii.stored(result.answer_text), result.intent,
                               result.grounding.to_dict(), served_from_cache=False,
                               leads=result.leads)

    payload = result.to_message_dict()
    payload["text"] = PiiVault.spoken(payload["text"])
    payload["ack"] = PiiVault.spoken(payload["ack"])
    payload["session_id"] = sid
    return payload
