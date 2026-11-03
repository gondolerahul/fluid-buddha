"""
Fast Router (Req 3.3.1) — latency masking.

Routes the utterance to a fast model to classify intent, infer persona, and
produce a sub-second acknowledgement phrase that is spoken immediately while the
Heavy Thinker works.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional, Sequence

from app.ai.base import ChatMessage, LLMClient
from app.config import Settings
from app.orchestrator.personas import valid_personas
from app.orchestrator.prompts import build_router_system

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class RouterResult:
    intent: str = "general"
    persona: Optional[str] = None
    persona_confidence: float = 0.0  # 0..1 — how strong the persona signal was
    persona_explicit: bool = False   # the visitor stated their segment outright
    ack: str = "Let me look that up for you."


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    m = _JSON_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


class FastRouter:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def route(
        self, user_text: str, history: Sequence[ChatMessage] = (),
        site_key: str = "hirebuddha",
    ) -> RouterResult:
        messages = list(history) + [ChatMessage(role="user", text=user_text)]
        try:
            resp = await self._llm.generate(
                system=build_router_system(site_key),
                messages=messages,
                tools=None,
                model=self._settings.fast_model,
                temperature=0.2,
                max_output_tokens=120,
            )
            data = _extract_json(resp.text)
        except Exception as exc:  # graceful degradation
            logger.warning("Fast Router failed (%s); using fallback", exc)
            data = {}

        persona = data.get("persona")
        if persona not in valid_personas(site_key):
            persona = None
        try:
            confidence = float(data.get("persona_confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        return RouterResult(
            intent=data.get("intent", "general"),
            persona=persona,
            persona_confidence=confidence if persona else 0.0,
            persona_explicit=bool(data.get("persona_explicit", False)),
            ack=data.get("ack") or "Let me look that up for you.",
        )
