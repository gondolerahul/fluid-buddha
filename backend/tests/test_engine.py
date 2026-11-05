"""
Engine quality (WS5): binary audio frames, pipelined + streamed TTS, and
follow-up query rewriting.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.ai.base import ChatMessage
from app.ai.vertex import GeminiTTS, PcmFramer
from app.main import app
from app.orchestrator.rewrite import depends_on_history, is_followup, retrieval_query
from app.transport.envelope import pack_audio, unpack_audio
from app.transport.websocket import _MAX_UTTERANCE_BYTES, VoiceSession


def _run(coro):
    """Run an async body, then dispose the shared engine so the next loop (or
    the TestClient's) gets pool connections bound to a live loop."""
    from app.db import dispose_engine

    async def wrapper():
        try:
            return await coro
        finally:
            await dispose_engine()
    return asyncio.run(wrapper())


# ---- binary audio frames ---------------------------------------------------

def test_audio_frame_roundtrip():
    pcm = bytes(range(256)) * 4
    frame = pack_audio("utt_abc123", pcm)
    assert len(frame) == 2 + len("utt_abc123") + len(pcm)
    assert unpack_audio(frame) == ("utt_abc123", pcm)
    assert unpack_audio(pack_audio(None, b"\x01\x00")) == ("", b"\x01\x00")
    # Not an audio frame / truncated header.
    assert unpack_audio(b"") is None
    assert unpack_audio(b"\x02\x00abc") is None
    assert unpack_audio(b"\x01\x09abc") is None


def test_ws_binary_audio_frames_carry_the_segment_id():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha&audio=binary") as ws:
            ready = ws.receive_json()
            assert ready["payload"]["config"]["audio_frames"] == "binary"
            # A malformed text frame is ignored, not fatal.
            ws.send_text("not json")
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "How do you integrate with our API?"}})
            open_ids: list[str] = []
            frames, ends = 0, 0
            for _ in range(600):
                msg = ws.receive()
                if msg.get("bytes") is not None:
                    sid, pcm = unpack_audio(msg["bytes"])
                    assert sid == open_ids[-1], "audio frame outside its segment"
                    assert pcm and len(pcm) % 2 == 0
                    frames += 1
                    continue
                import json
                env = json.loads(msg["text"])
                if env["channel"] == "AUDIO":
                    assert env["type"] != "chunk", "binary client got a JSON chunk"
                    if env["type"] == "start":
                        open_ids.append(env["sync_id"])
                    elif env["type"] == "end":
                        ends += 1
                        if ends >= 2:
                            break
            assert frames > 0 and ends >= 2


def test_ws_json_audio_stays_the_default():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
            assert ws.receive_json()["payload"]["config"]["audio_frames"] == "json"


def _session(**settings) -> VoiceSession:
    st = SimpleNamespace(audio_cache_enabled=False, tts_sample_rate=24000, **settings)
    rt = SimpleNamespace(settings=st, engines=SimpleNamespace(tts=None))
    return VoiceSession(_FakeWs(), rt)


class _FakeWs:
    def __init__(self) -> None:
        self.sent: list = []

    async def send_json(self, env) -> None:
        self.sent.append(("json", env))

    async def send_bytes(self, data) -> None:
        self.sent.append(("bytes", data))


def test_binary_mic_chunks_buffer_after_consent_and_are_capped():
    s = _session()
    chunk = b"\x00\x01" * 800

    async def go():
        await s._on_binary(pack_audio(None, chunk))     # before consent: dropped
        assert s._audio == []
        assert s.ws.sent[-1][1]["type"] == "consent_required"
        s._consent_at = object()
        await s._on_binary(pack_audio(None, chunk))
        await s._on_binary(b"\x07junk")                  # unknown kind: ignored
        assert s._audio == [chunk]
        s._audio_bytes = _MAX_UTTERANCE_BYTES - 10       # a minute already held
        await s._on_binary(pack_audio(None, chunk))
        assert len(s._audio) == 1
    _run(go())


# ---- pipelined TTS -------------------------------------------------------

class _SlowTTS:
    """Each segment takes `delay` to produce its first audio."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.started: list[str] = []
        self.cancelled = 0

    async def synthesize_stream(self, text):
        self.started.append(text)
        try:
            await asyncio.sleep(self.delay)
            for _ in range(2):
                yield b"\x00\x00" * 100
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            self.cancelled += 1
            raise


ANSWER = ("The first sentence is long enough to stand alone. "
          "The second sentence is long enough as well. "
          "And a third one closes the answer out.")


def test_speak_synthesises_the_next_segment_ahead():
    s = _session()
    tts = _SlowTTS(0.25)
    s.rt.engines.tts = tts

    async def go():
        t0 = time.monotonic()
        await s._speak(ANSWER, "utt_first")
        return time.monotonic() - t0
    elapsed = _run(go())
    assert len(tts.started) == 3
    # Sequential synthesis would take 3 × 0.25 s; one-ahead overlaps them.
    assert elapsed < 0.65, elapsed

    # Audio stays in order: every chunk sits between its own start and end.
    current = None
    order = []
    for kind, env in s.ws.sent:
        if env["channel"] == "AUDIO" and env["type"] == "start":
            current = env["sync_id"]
            order.append(current)
        elif env["channel"] == "AUDIO" and env["type"] == "end":
            assert env["sync_id"] == current
            current = None
        else:
            assert env["type"] == "chunk" and env["sync_id"] == current
    assert order[0] == "utt_first" and len(order) == 3


def test_speak_cancel_stops_synthesis_ahead():
    s = _session()
    tts = _SlowTTS(5.0)
    s.rt.engines.tts = tts

    async def go():
        task = asyncio.create_task(s._speak(ANSWER, "utt_first"))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0)
    _run(go())
    assert tts.cancelled == 2  # the segment being sent and the one ahead


def test_tts_failure_ends_the_segment_but_keeps_the_text():
    class Broken:
        async def synthesize_stream(self, text):
            raise RuntimeError("tts down")
            yield b""  # pragma: no cover

    s = _session()
    s.rt.engines.tts = Broken()
    _run(s._speak("Short answer here, still shown.", "utt_x"))
    types = [(env["type"], env["payload"].get("text")) for _, env in s.ws.sent]
    assert types[0] == ("start", "Short answer here, still shown.")
    assert types[-1][0] == "end"


# ---- streamed Gemini TTS -------------------------------------------------

def test_pcm_framer_strips_wav_header_and_keeps_samples_whole():
    f = PcmFramer(sample_rate=1000)            # 400-byte frames
    header = b"RIFF" + b"\x00" * 40
    out = f.push(header[:10])                  # header split across parts
    assert out == []
    out = f.push(header[10:] + b"\x01" * 450)
    assert out == [b"\x01" * 400]
    out = f.push(b"\x02" * 5)
    assert out == []
    assert f.flush() == b"\x01" * 50 + b"\x02" * 4   # odd byte dropped


def _part(data: bytes):
    return SimpleNamespace(inline_data=SimpleNamespace(data=data))


def _resp(*datas: bytes):
    return SimpleNamespace(candidates=[SimpleNamespace(
        content=SimpleNamespace(parts=[_part(d) for d in datas]))])


def _gemini(models) -> GeminiTTS:
    tts = GeminiTTS.__new__(GeminiTTS)
    tts.sample_rate = 1000
    tts._model = "m"
    tts._voice = "v"
    tts._config = lambda language="": None
    tts._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return tts


async def _collect(agen) -> bytes:
    out = b""
    async for c in agen:
        out += c
    return out


def test_gemini_tts_streams_parts_as_they_arrive():
    calls = []

    class Models:
        async def generate_content_stream(self, **kw):
            calls.append("stream")

            async def gen():
                yield _resp(b"\x01" * 500)
                yield _resp(b"\x02" * 300)
            return gen()

        async def generate_content(self, **kw):  # pragma: no cover
            calls.append("one-shot")
            return _resp()

    pcm = _run(_collect(_gemini(Models()).synthesize_stream("hi")))
    assert pcm == b"\x01" * 500 + b"\x02" * 300
    assert calls == ["stream"]


def test_gemini_tts_falls_back_when_streaming_fails():
    class Models:
        async def generate_content_stream(self, **kw):
            raise RuntimeError("streaming not supported for this model")

        async def generate_content(self, **kw):
            return _resp(b"RIFF" + b"\x00" * 40 + b"\x03" * 600)

    pcm = _run(_collect(_gemini(Models()).synthesize_stream("hi")))
    assert pcm == b"\x03" * 600


# ---- follow-up query rewriting -------------------------------------------

def _history(*user_turns: str) -> list[ChatMessage]:
    out = []
    for t in user_turns:
        out += [ChatMessage(role="user", text=t), ChatMessage(role="model", text="ok")]
    return out


def test_followup_detection():
    for q in ("How much is it?", "and the enterprise plan?", "What about Slack?",
              "Tell me more", "Does that include support?", "why?"):
        assert is_followup(q), q
    for q in ("How does HireBuddha screen candidates?", "pricing",
              "Can your agents book interviews automatically for large teams "
              "across several time zones?"):
        assert not is_followup(q), q


def test_retrieval_query_folds_in_the_earlier_question():
    h = _history("Tell me about the Pro plan")
    assert retrieval_query("How much is it?", h) == "Tell me about the Pro plan How much is it?"
    # A chain of follow-ups reaches back to the question that had the subject.
    h2 = _history("Tell me about the Pro plan", "how much is it?")
    assert retrieval_query("and does that include support?", h2) == (
        "Tell me about the Pro plan how much is it? and does that include support?")
    # Self-contained questions and empty history pass through.
    assert retrieval_query("How do refunds work?", h) == "How do refunds work?"
    assert retrieval_query("How much is it?", []) == "How much is it?"
    # The synthetic welcome turn isn't a question to fold in.
    welcome = [ChatMessage(role="user", text="(visitor arrived on the page)"),
               ChatMessage(role="model", text="Hi!")]
    assert retrieval_query("tell me more", welcome) == "tell me more"
    assert not depends_on_history("tell me more", welcome)
    assert depends_on_history("tell me more", h)


def test_chat_followup_is_answered_fresh_and_not_cached():
    """A mid-conversation follow-up is neither replayed nor recorded (WS5)."""
    import uuid

    from app.cortex.episodic import EpisodicCache
    from app.cortex.providers import build_cortex_providers
    from app.config import get_settings
    from app.db import session_scope

    site = f"followup-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        app.state.runtime.settings.episodic_min_episodes = 1
        first = client.post("/chat", json={
            "site": site, "message": "Tell me about the screening agent"}).json()
        sid = first["session_id"]
        client.post("/chat", json={"site": site, "session_id": sid,
                                   "message": "How much is it?"})

    async def questions():
        settings = get_settings()
        async with session_scope() as db:
            cache = EpisodicCache(db, settings, build_cortex_providers(settings),
                                  site_key=site)
            rows, _ = await cache.list_entries(limit=50)
            return [r["question"] for r in rows]
    qs = _run(questions())
    assert "Tell me about the screening agent" in qs
    assert "How much is it?" not in qs
