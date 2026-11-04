"""
Lean conversational responder (Hybrid architecture, Req 3 follow-up).

For ordinary conversational turns — greetings, capability questions, follow-ups —
the full grounded tool-calling loop (5+ LLM round-trips) is overkill and is the
main source of latency. The lean path instead does ONE retrieval up front and ONE
generation: retrieve grounding → inject snippets → answer. The orchestrator
escalates to the Heavy Thinker only when a turn actually needs a diagram, page,
navigation, or deep multi-step grounding (see ``needs_heavy``).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional, Sequence

from app.ai.base import ChatMessage, LLMClient
from app.config import Settings
from app.cortex.bridge import CortexBridge
from app.cortex.query import citations, query_cortex
from app.orchestrator.prompts import build_lean_system
from app.orchestrator.result import Grounding
from app.orchestrator.rewrite import retrieval_query
from app.orchestrator.thinker import ThinkResult

logger = logging.getLogger(__name__)

# Signals that a turn wants the heavy path (a visual, a page, navigation, or
# explicit numbers/comparisons). Everything else takes the fast lean path.
_HEAVY_INTENTS = {"pricing_roi", "integration", "navigation"}
_HEAVY_KW = re.compile(
    r"\b(show|diagram|chart|graph|table|compare|comparison|calculat|roi|pricing|"
    r"price|cost|quote|integrat|navigat|take me|go to|scroll|walk me|draw|visual|"
    r"generate|build me|demo|tour)\b",
    re.IGNORECASE,
)


# A correction while a component is on screen ("actually we have 50 seats")
# needs the Heavy Thinker's patch_component tool (D-11).
_CORRECTION_KW = re.compile(
    r"\b(actually|instead|change|update|make it|correct|adjust|set it|not \d+)\b",
    re.IGNORECASE,
)


# A raw email, or its masked placeholder (WS8).
_EMAIL_KW = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}|<EMAIL_\d+>", re.IGNORECASE)


def needs_heavy(transcript: str, intent: str = "general", *,
                has_components: bool = False) -> bool:
    """Decide whether a turn must use the Heavy Thinker (tools/diagrams/nav)."""
    if intent in _HEAVY_INTENTS:
        return True
    if has_components and _CORRECTION_KW.search(transcript or ""):
        return True
    if _EMAIL_KW.search(transcript or ""):
        return True   # contact details → capture_lead needs the tool loop
    return bool(_HEAVY_KW.search(transcript or ""))


class LeanResponder:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def respond(
        self,
        *,
        user_text: str,
        persona: Optional[str],
        bridge: CortexBridge,
        history: Sequence[ChatMessage] = (),
        site_key: str = "hirebuddha",
        page: Optional[str] = None,
        section: Optional[str] = None,
        related: Optional[list] = None,
        probe: bool = False,
    ) -> ThinkResult:
        t0 = time.monotonic()
        # 1. One grounding retrieval (no tool round-trip). A follow-up ("how
        #    much is it?") searches with the question it follows (WS5).
        query = retrieval_query(user_text, history)
        if query != user_text:
            logger.info("lean: follow-up retrieval query %r", query[:120])
        res = await query_cortex(
            bridge,
            query,
            top_k=self._settings.cortex_retrieval_top_k,
            threshold=self._settings.cortex_confidence_threshold,
        )
        grounding = Grounding(
            confidence=res["confidence"],
            found=res["found"],
            sources=citations(res.get("snippets", [])),
        )
        # 2. One generation, grounded by the injected snippets.
        system = build_lean_system(
            persona, site_key, res.get("snippets", []),
            page=page, section=section, related=related, probe=probe,
        )
        messages = list(history) + [ChatMessage(role="user", text=user_text)]
        resp = await self._llm.generate(
            system=system,
            messages=messages,
            tools=None,
            model=self._settings.fast_model,
            temperature=0.5,
            max_output_tokens=400,
            thinking_budget=0,
        )
        answer = resp.text.strip() or (
            "Here's what I can tell you — want me to go deeper on any part?"
            if grounding.found
            else "I want to get this exactly right — let me connect you with the team."
        )
        logger.info(
            "lean done in %.1fs: grounded=%s answer_len=%d",
            time.monotonic() - t0, grounding.found, len(answer),
        )
        from app.analytics.pricing import estimate_tokens
        in_tok = resp.input_tokens or (
            estimate_tokens(system) + sum(estimate_tokens(m.text) for m in messages)
        )
        out_tok = resp.output_tokens or estimate_tokens(resp.text)
        return ThinkResult(
            answer_text=answer, grounding=grounding,
            llm_kind="fast", input_tokens=int(in_tok), output_tokens=int(out_tok),
        )
