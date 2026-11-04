"""
Real Vertex AI engines.

* LLM + embeddings via the unified ``google-genai`` SDK (Vertex backend).
* ASR via Google Cloud Speech-to-Text (async streaming).
* TTS via Google Cloud Text-to-Speech (LINEAR16 PCM).

All Google imports are lazy so this module imports fine in mock mode / CI.
Activated only when ``MOCK_AI=false``; requires ``GOOGLE_CLOUD_PROJECT`` and
Application Default Credentials (or ``GOOGLE_APPLICATION_CREDENTIALS``).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Optional

from app.ai.base import (
    ChatMessage,
    LLMResponse,
    ToolCall,
    ToolSpec,
    TranscriptEvent,
)
from app.config import Settings, vertex_model_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini LLM (function calling) + embeddings
# ---------------------------------------------------------------------------

class VertexLLMClient:
    def __init__(self, settings: Settings) -> None:
        from google import genai  # lazy

        self._settings = settings
        self._genai = genai
        self._client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )

    def _to_contents(self, messages: Sequence[ChatMessage]) -> list[Any]:
        from google.genai import types

        contents: list[Any] = []
        i = 0
        n = len(messages)
        while i < n:
            m = messages[i]
            if m.role == "tool":
                # Coalesce CONSECUTIVE tool responses into a single tool turn:
                # Gemini requires the number of function_response parts to equal
                # the number of function_call parts in the preceding model turn,
                # so a parallel multi-call turn must be answered in one turn.
                parts = []
                while i < n and messages[i].role == "tool":
                    tm = messages[i]
                    parts.append(types.Part.from_function_response(
                        name=tm.tool_name or "tool",
                        response={"result": tm.tool_result},
                    ))
                    i += 1
                contents.append(types.Content(role="tool", parts=parts))
                continue
            if m.role == "model" and m.tool_calls:
                contents.append(types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(name=c.name, args=c.args),
                            # Gemini 3.x requires the original thought signature
                            # to be replayed alongside the function call.
                            thought_signature=c.thought_signature,
                        )
                        for c in m.tool_calls
                    ],
                ))
            else:
                role = "model" if m.role == "model" else "user"
                contents.append(types.Content(
                    role=role, parts=[types.Part.from_text(text=m.text)]
                ))
            i += 1
        return contents

    def _to_tools(self, tools: Optional[Sequence[ToolSpec]]):
        if not tools:
            return None
        from google.genai import types

        decls = [
            types.FunctionDeclaration(
                name=t.name, description=t.description, parameters=t.parameters
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=decls)]

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
    ) -> LLMResponse:
        from google.genai import types

        cfg_kwargs: dict[str, Any] = dict(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=self._to_tools(tools),
        )
        # Gemini 3.x "thinking" tokens count against max_output_tokens; pass
        # thinking_budget=0 to disable thinking when we just need the answer text.
        if thinking_budget is not None:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=thinking_budget
            )
        # We drive the function-calling loop ourselves; disable the SDK's own
        # Automatic Function Calling so it can't add a second hidden loop.
        if tools:
            cfg_kwargs["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
        cfg = types.GenerateContentConfig(**cfg_kwargs)
        used_model = vertex_model_id(model or self._settings.heavy_model)
        resp = await self._client.aio.models.generate_content(
            model=used_model, contents=self._to_contents(messages), config=cfg
        )
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        cand = (resp.candidates or [None])[0]
        if cand and cand.content and cand.content.parts:
            for part in cand.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        name=fc.name,
                        args=dict(fc.args or {}),
                        thought_signature=getattr(part, "thought_signature", None),
                    ))
                elif getattr(part, "text", None):
                    # Skip Gemini 3.x "thinking" parts — only the real answer text.
                    if getattr(part, "thought", False):
                        continue
                    text_parts.append(part.text)
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            model=used_model,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        )

    async def generate_stream(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        used_model = vertex_model_id(model or self._settings.heavy_model)
        stream = await self._client.aio.models.generate_content_stream(
            model=used_model, contents=self._to_contents(messages), config=cfg
        )
        async for chunk in stream:
            if getattr(chunk, "text", None):
                yield chunk.text


class VertexEmbedder:
    """768-dim embeddings (matches the cortex schema)."""

    def __init__(self, settings: Settings) -> None:
        from google import genai

        self._settings = settings
        self._model = settings.embed_model
        self._dim = settings.embed_dim
        self._client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )

    def dimension(self) -> int:
        return self._dim

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        from google.genai import types

        resp = await self._client.aio.models.embed_content(
            model=self._model,
            contents=list(texts),
            config=types.EmbedContentConfig(output_dimensionality=self._dim),
        )
        return [list(e.values) for e in (resp.embeddings or [])]


# ---------------------------------------------------------------------------
# ASR — Cloud Speech-to-Text (async streaming)
# ---------------------------------------------------------------------------

class VertexASR:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def transcribe_stream(
        self, audio: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]:
        from google.cloud import speech_v1 as speech

        client = speech.SpeechAsyncClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=self._settings.asr_language,
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config, interim_results=True
        )

        async def requests() -> AsyncIterator[Any]:
            yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
            async for chunk in audio:
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        responses = await client.streaming_recognize(requests=requests())
        async for response in responses:
            for result in response.results:
                if not result.alternatives:
                    continue
                alt = result.alternatives[0]
                yield TranscriptEvent(
                    text=alt.transcript,
                    is_final=result.is_final,
                    confidence=getattr(alt, "confidence", 1.0) or 1.0,
                )


# ---------------------------------------------------------------------------
# TTS — Gemini native TTS (natural prosody) via google-genai
# ---------------------------------------------------------------------------

class GeminiTTS:
    """Gemini native text-to-speech.

    Uses ``generate_content`` with ``response_modalities=["AUDIO"]`` and a
    prebuilt Gemini voice. The model returns raw little-endian PCM16 mono at
    24 kHz (audio/L16;rate=24000) — no WAV header — which we chunk to ~200 ms
    frames for the frontend jitter buffer. Far more natural than Cloud TTS
    Neural2 voices.

    Audio is streamed (WS5): each part is forwarded as the model produces it,
    so playback starts before the whole sentence is synthesised. If streaming
    fails before any audio arrives, the one-shot call is used instead.
    """

    def __init__(self, settings: Settings) -> None:
        from google import genai

        self._settings = settings
        self.sample_rate = settings.tts_sample_rate
        self._model = vertex_model_id(settings.tts_model)
        self._voice = settings.tts_gemini_voice
        self._client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.vertex_location,
        )

    def _config(self):
        from google.genai import types

        return types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._voice
                    )
                )
            ),
        )

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        frames = PcmFramer(self.sample_rate)
        sent = False
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self._model, contents=text, config=self._config()
            )
            async for resp in stream:
                for data in _audio_parts(resp):
                    for frame in frames.push(data):
                        sent = True
                        yield frame
        except Exception as exc:
            if sent:
                raise
            logger.info("Gemini TTS streaming unavailable (%s); using one-shot", exc)
            frames = PcmFramer(self.sample_rate)  # drop any partial stream
            resp = await self._client.aio.models.generate_content(
                model=self._model, contents=text, config=self._config()
            )
            for data in _audio_parts(resp):
                for frame in frames.push(data):
                    yield frame
        tail = frames.flush()
        if tail:
            yield tail


def _audio_parts(resp) -> list[bytes]:
    """The inline audio bytes of one (possibly partial) Gemini response."""
    out = []
    cand = (getattr(resp, "candidates", None) or [None])[0]
    content = getattr(cand, "content", None)
    for part in (getattr(content, "parts", None) or []):
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            out.append(inline.data)
    return out


class PcmFramer:
    """Re-chunks streamed PCM16 into ~200 ms frames for the jitter buffer,
    dropping a WAV header some backends prepend and never splitting a sample."""

    def __init__(self, sample_rate: int) -> None:
        self._frame = sample_rate * 2 // 5  # ~200ms of 16-bit mono
        self._buf = bytearray()
        self._started = False

    def push(self, data: bytes) -> list[bytes]:
        self._buf.extend(data)
        if not self._started:
            if len(self._buf) < 4:
                return []
            if self._buf[:4] == b"RIFF":
                if len(self._buf) < 44:
                    return []
                del self._buf[:44]
            self._started = True
        out = []
        while len(self._buf) >= self._frame:
            out.append(bytes(self._buf[:self._frame]))
            del self._buf[:self._frame]
        return out

    def flush(self) -> bytes:
        n = len(self._buf) - len(self._buf) % 2
        tail = bytes(self._buf[:n])
        self._buf.clear()
        return tail


# ---------------------------------------------------------------------------
# TTS — Cloud Text-to-Speech (LINEAR16 PCM) — legacy fallback
# ---------------------------------------------------------------------------

class VertexTTS:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.sample_rate = settings.tts_sample_rate

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        from google.cloud import texttospeech_v1 as tts

        client = tts.TextToSpeechAsyncClient()
        voice = tts.VoiceSelectionParams(
            language_code=self._settings.asr_language, name=self._settings.tts_voice
        )
        audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.sample_rate,
        )
        resp = await client.synthesize_speech(
            input=tts.SynthesisInput(text=text), voice=voice, audio_config=audio_config
        )
        # Strip the 44-byte WAV header so the frontend receives raw PCM16.
        pcm = resp.audio_content[44:] if resp.audio_content[:4] == b"RIFF" else resp.audio_content
        chunk = self.sample_rate * 2 // 5  # ~200ms
        for i in range(0, len(pcm), chunk):
            yield pcm[i:i + chunk]
