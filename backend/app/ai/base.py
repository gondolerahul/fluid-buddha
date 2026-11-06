"""
Provider-neutral AI engine interfaces.

The orchestrator depends only on these abstractions. Two implementations exist:
``vertex.py`` (real Vertex AI / Gemini) and ``mock.py`` (deterministic stubs for
credential-free local runs). ``factory.py`` picks one based on ``MOCK_AI``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Chat / function-calling LLM
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    """One turn of conversation. ``role`` is 'user' | 'model' | 'tool'.

    A ``model`` turn that issued function calls carries them in ``tool_calls`` so
    the next request replays the call before its ``tool`` response (Vertex
    function-calling requires this ordering).
    """
    role: str
    text: str = ""
    # For role == 'tool': which tool produced this and its JSON-able payload.
    tool_name: Optional[str] = None
    tool_result: Any = None
    # For role == 'model': the function calls this turn issued.
    tool_calls: Optional[list["ToolCall"]] = None
    # For role == 'model': the provider's own record of the turn (e.g. Claude's
    # content blocks with their thinking blocks), replayed verbatim by the
    # engine that produced it; other engines ignore it (M3-4).
    raw: Any = None


@dataclass
class ToolSpec:
    """A function the model may call. ``parameters`` is a JSON-schema object."""
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    # Opaque provider token (Gemini 3.x "thought signature"): returned with a
    # function call and MUST be replayed on the model turn or the next request
    # 400s. None for providers/models that don't use it (e.g. Gemini 2.x, mock).
    thought_signature: Optional[bytes] = None
    # The provider's id for this call (Claude ``tool_use.id``, OpenAI
    # ``tool_call.id``), echoed on its result. None where unused (Vertex, mock).
    id: Optional[str] = None


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    finish_reason: str = "stop"
    # Token accounting for cost analytics (req F). Real engines fill these from
    # provider usage metadata; the mock leaves them 0 and callers estimate.
    input_tokens: int = 0
    output_tokens: int = 0
    # Which provider answered (M3-4: "vertex", "anthropic", "openai",
    # "azure_openai", "mock") and its native turn record for replay (see
    # ``ChatMessage.raw``).
    provider: str = ""
    raw: Any = None


@runtime_checkable
class LLMClient(Protocol):
    """Single-shot and streaming generation with optional function calling."""

    async def generate(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Optional[Sequence[ToolSpec]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        thinking_budget: Optional[int] = None,
    ) -> LLMResponse: ...

    async def generate_stream(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]: ...


# ---------------------------------------------------------------------------
# Speech (ASR / TTS)
# ---------------------------------------------------------------------------

@dataclass
class TranscriptEvent:
    text: str
    is_final: bool
    confidence: float = 1.0
    language: str = ""      # the recogniser's language for this result, if it says


@runtime_checkable
class ASREngine(Protocol):
    """Streaming speech-to-text. Consumes PCM16 mono audio chunks."""

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes], languages: Sequence[str] = ()
    ) -> AsyncIterator[TranscriptEvent]: ...


@runtime_checkable
class TTSEngine(Protocol):
    """Streaming text-to-speech. Yields PCM16 audio chunks for the given text."""

    sample_rate: int

    async def synthesize_stream(self, text: str, language: str = "") -> AsyncIterator[bytes]: ...
