"""
Deterministic mock AI engines (MOCK_AI=true).

These let the full cognitive loop, transport, ingestion and HTTP/WS endpoints
run and be tested with NO Google Cloud credentials. The mock LLM faithfully
drives the real function-calling loop:

    turn 1 -> calls ``query_cortex`` (grounding first — never skipped)
    turn 2 -> may call client-action tools (render_component / navigate / …)
    turn 3 -> returns the spoken explanation, grounded in the retrieved snippet

so the orchestrator code path is identical to production.
"""
from __future__ import annotations

import json
import math
import re
import struct
from collections.abc import AsyncIterator, Sequence
from typing import Optional

from app.ai.base import (
    ChatMessage,
    LLMResponse,
    LLMClient,
    ToolCall,
    ToolSpec,
    TranscriptEvent,
)

# Tool names that represent client-side actions (vs. server-side retrieval).
_ACTION_TOOLS = {
    "render_component", "patch_component", "navigate", "scroll_to", "set_persona",
    "generate_page", "capture_lead",
}

_PERSONA_KEYWORDS = {
    "startups": ["startup", "founder", "seed", "early stage", "sme"],
    "solopreneurs": ["solo", "one-person", "freelance", "myself", "just me"],
    "enterprise": ["enterprise", "compliance", "procurement", "soc2", "large org"],
    "medium-enterprise": ["growing", "scale up", "mid-market", "operations", "ops team"],
}

_DEV_KEYWORDS = ["api", "integrat", "architecture", "webhook", "sdk", "technical", "deploy"]
_EXEC_KEYWORDS = ["roi", "cost", "pricing", "budget", "savings", "business case"]

# Correction of an on-screen component: "actually we have 50 seats" → patch it.
_ON_SCREEN_RE = re.compile(r"- sync_id (\S+): (\w+)")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
_SEATS_RE = re.compile(r"(\d+)\s*(?:seats|people|employees|users)", re.IGNORECASE)


def _last_user_text(messages: Sequence[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.text
    return ""


def _infer_persona(text: str) -> Optional[str]:
    low = text.lower()
    for persona, kws in _PERSONA_KEYWORDS.items():
        if any(k in low for k in kws):
            return persona
    return None


class MockLLMClient(LLMClient):
    """Rule-based stand-in for Gemini that still exercises tool calling."""

    def __init__(self, model: str = "mock-gemini") -> None:
        self.model = model

    async def generate(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Optional[Sequence[ToolSpec]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,  # ignored by the mock
    ) -> LLMResponse:
        used_model = model or self.model
        user_text = _last_user_text(messages)
        low = user_text.lower()
        tool_names = {t.name for t in (tools or [])}

        # --- Live component reaction (no tools, deterministic quip) ----------
        if not tools and "interacting with" in system.lower():
            return LLMResponse(
                text="At those numbers, the return looks compelling.",
                model=used_model,
            )

        # --- Fast Router (no tools): return JSON intent/persona/ack ----------
        if not tools and "router" in system.lower():
            persona = _infer_persona(user_text)
            if any(k in low for k in _DEV_KEYWORDS):
                intent = "capability"
            elif any(k in low for k in _EXEC_KEYWORDS):
                intent = "pricing_roi"
            elif any(k in low for k in ["hello", "hi ", "hey"]):
                intent = "greeting"
            else:
                intent = "general"
            ack = {
                "capability": "Great question — let me map that out for you.",
                "pricing_roi": "Sure, let me pull up the numbers.",
                "greeting": "Hi! I'm Pragya. Ask me anything about the platform.",
                "general": "Let me look that up for you.",
            }[intent]
            # Deterministic persona confidence so the adaptive-switch / probe
            # logic is exercisable in mock mode: explicit self-ID phrases score
            # high; a bare keyword match is a softer signal.
            explicit = any(p in low for p in (
                "i run", "i'm a", "i am a", "we are a", "we're a", "my company",
                "person company", "-person",
            ))
            confidence = 0.0 if not persona else (0.92 if explicit else 0.65)
            payload = {
                "intent": intent,
                "persona": persona,
                "persona_confidence": confidence,
                "persona_explicit": explicit and persona is not None,
                "ack": ack,
            }
            return LLMResponse(text=json.dumps(payload), model=used_model)

        has_cortex = any(m.role == "tool" and m.tool_name == "query_cortex" for m in messages)
        has_action = any(m.role == "tool" and m.tool_name in _ACTION_TOOLS for m in messages)

        # --- Heavy Thinker turn 1: ground first ------------------------------
        if "query_cortex" in tool_names and not has_cortex:
            return LLMResponse(
                tool_calls=[ToolCall("query_cortex", {"query": user_text})],
                model=used_model,
            )

        # --- Heavy Thinker turn 2: client actions ----------------------------
        if has_cortex and not has_action:
            calls = self._patch_on_screen(user_text, tool_names, system) \
                or self._decide_actions(low, tool_names)
            if calls:
                return LLMResponse(tool_calls=calls, model=used_model)

        # --- Final spoken answer (grounded) ----------------------------------
        return LLMResponse(text=self._compose_answer(user_text, messages), model=used_model)

    @staticmethod
    def _patch_on_screen(user_text: str, tool_names: set[str], system: str) -> list[ToolCall]:
        """A seat-count correction updates the latest on-screen ROI calculator."""
        if "patch_component" not in tool_names:
            return []
        seats = _SEATS_RE.search(user_text)
        calcs = [sid for sid, ctype in _ON_SCREEN_RE.findall(system)
                 if ctype == "roi_calculator"]
        if not seats or not calcs:
            return []
        return [ToolCall("patch_component", {
            "target_sync_id": calcs[-1], "patch": {"seats": int(seats.group(1))},
            "animation": "count_up",
        })]

    def _decide_actions(self, low: str, tool_names: set[str]) -> list[ToolCall]:
        calls: list[ToolCall] = []
        email = _EMAIL_RE.search(low)
        if email and "capture_lead" in tool_names:
            calls.append(ToolCall("capture_lead", {"email": email.group(0)}))
        persona = _infer_persona(low)
        if persona and "set_persona" in tool_names:
            calls.append(ToolCall("set_persona", {"persona": persona}))
        # Extreme tier: the host has no pages — build one (instead of rendering a
        # single component into the panel).
        if "generate_page" in tool_names:
            calls.append(ToolCall("generate_page", {
                "title": "Welcome",
                "sections": [
                    {"type": "hero", "props": {
                        "title": "Built for you, right now",
                        "subtitle": "This page was generated at runtime.",
                        "cta_label": "Get in touch"}},
                    {"type": "text", "props": {"body": "Here's what we offer."}},
                    {"type": "enquiry_form", "props": {
                        "title": "Ask us anything",
                        "fields": [
                            {"name": "name", "label": "Name", "type": "text"},
                            {"name": "email", "label": "Email", "type": "email"},
                            {"name": "message", "label": "Message", "type": "textarea"},
                        ],
                        "submit_label": "Send",
                        "operation_id": "submit_enquiry"}},
                ],
            }))
            return calls
        if "render_component" in tool_names:
            if any(k in low for k in _EXEC_KEYWORDS):
                calls.append(ToolCall("render_component", {
                    "component_type": "roi_calculator",
                    "initial_state": {"seats": 10, "monthly_cost": 10000, "hours_saved": 320},
                    "explanation_text": "Here's a quick ROI model you can adjust.",
                }))
            elif any(k in low for k in _DEV_KEYWORDS):
                calls.append(ToolCall("render_component", {
                    "component_type": "flowchart",
                    "initial_state": {"nodes": [
                        {"id": "n1", "label": "Your system"},
                        {"id": "n2", "label": "HireBuddha API"},
                        {"id": "n3", "label": "AI Employee"},
                    ], "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}]},
                    "explanation_text": "This is how the integration flows.",
                }))
        if "navigate" in tool_names:
            if "pricing" in low:
                calls.append(ToolCall("navigate", {"path": "/pricing"}))
            elif "security" in low:
                calls.append(ToolCall("navigate", {"path": "/product/security"}))
        return calls

    def _compose_answer(self, user_text: str, messages: Sequence[ChatMessage]) -> str:
        # Pull the cortex tool result to ground the answer / drive the guardrail.
        snippet = ""
        confidence = 0.0
        for m in messages:
            if m.role == "tool" and m.tool_name == "query_cortex":
                try:
                    data = m.tool_result if isinstance(m.tool_result, dict) else json.loads(m.tool_result)
                    confidence = float(data.get("confidence", 0.0))
                    if data.get("snippets"):
                        snippet = data["snippets"][0].get("text", "")[:280]
                except Exception:
                    pass
        if confidence < 0.45 or not snippet:
            return (
                "I don't have a grounded answer for that specific point yet, "
                "but I can connect you with the team or point you to the closest "
                "capability we do support. Want me to do that?"
            )
        return f"{snippet.strip()} Want me to go deeper on any part of that?"

    async def generate_stream(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        text = self._compose_answer(_last_user_text(messages), messages)
        for word in text.split(" "):
            yield word + " "


class MockASR:
    """Placeholder ASR. Real transcripts come via the AUDIO `end` override in
    mock mode; this only fires if raw audio is streamed with no transcript."""

    async def transcribe_stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptEvent]:
        async for _ in audio:
            pass
        yield TranscriptEvent(text="", is_final=True, confidence=0.0)


class MockTTS:
    """Emits PCM16 silence of a duration proportional to the text length, so the
    frontend audio pipeline / jitter buffer can be exercised end-to-end."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        words = max(1, len(text.split()))
        total_seconds = min(12.0, max(0.6, words * 0.32))
        chunk_seconds = 0.2
        samples_per_chunk = int(self.sample_rate * chunk_seconds)
        chunks = int(math.ceil(total_seconds / chunk_seconds))
        silence = struct.pack(f"<{samples_per_chunk}h", *([0] * samples_per_chunk))
        for _ in range(chunks):
            yield silence
