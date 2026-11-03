"""
Conversation-cache tests (Feature 2). Mock mode + pgvector:

    MOCK_AI=true python -m pytest tests/test_cache.py -q

Exercises the audio byte cache, exact-question replay, persona scoping, and the
end-to-end chat replay path (verbatim answer reused on the second ask).
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.cortex.episodic import EpisodicCache, normalize_question
from app.cortex.providers import build_cortex_providers
from app.db import dispose_engine, init_db, session_scope
from app.transport.answer_audio import AnswerAudioCache, audio_key

SITE = "cachetest"


def _run(coro):
    """Run an async body, then dispose the engine so the next ``asyncio.run`` (or
    the TestClient on its own loop) gets pool connections bound to a live loop."""
    async def wrapper():
        try:
            return await coro
        finally:
            await dispose_engine()
    return asyncio.run(wrapper())


def test_normalize_question():
    assert normalize_question("  How   does  PRICING work? ") == "how does pricing work?"


def test_audio_key_stable_and_voice_sensitive():
    a = audio_key("Hello there.", voice="Aoede", sample_rate=24000)
    b = audio_key("Hello   there.", voice="Aoede", sample_rate=24000)  # ws-normalised
    c = audio_key("Hello there.", voice="Other", sample_rate=24000)
    assert a == b and a != c


def test_audio_cache_roundtrip():
    key_box = {}

    async def go():
        await init_db()
        async with session_scope() as db:
            cache = AnswerAudioCache(db, get_settings())
            key_box["k"] = cache.key("unit-seg-" + uuid.uuid4().hex)
            assert await cache.get(key_box["k"]) is None
            await cache.put(key_box["k"], SITE, b"\x01\x02\x03\x04")
        async with session_scope() as db:
            cache = AnswerAudioCache(db, get_settings())
            assert await cache.get(key_box["k"]) == b"\x01\x02\x03\x04"

    _run(go())


def test_conversation_cache_exact_replay_and_persona_scope():
    q = "Unique cache probe " + uuid.uuid4().hex + "?"

    async def go():
        await init_db()
        settings = get_settings()
        providers = build_cortex_providers(settings)
        async with session_scope() as db:
            cache = EpisodicCache(db, settings, providers, site_key=SITE)
            await cache.record(
                question=q, answer_text="The cached answer.",
                components=[{
                    "sync_id": "ui_seed", "component_type": "table",
                    "initial_state": {"headers": ["a"], "rows": [["1"]]},
                    "explanation_text": "t",
                }],
                actions=[{"type": "navigate", "path": "/pricing"}],
                persona="startups", page="/", channel="text",
            )
        async with session_scope() as db:
            cache = EpisodicCache(db, settings, providers, site_key=SITE)
            hits = await cache.query(transcript=q, persona="startups", page="/", top_k=3)
            assert hits, "expected an exact match"
            assert hits[0].match == "exact" and hits[0].score == 1.0
            assert hits[0].answer_text == "The cached answer."
            assert hits[0].components[0]["component_type"] == "table"
            assert hits[0].actions[0]["path"] == "/pricing"
            # A different persona must not exact-match a startups-only row.
            other = await cache.query(transcript=q, persona="enterprise", top_k=3)
            assert all(h.match != "exact" for h in other)
            assert await cache.count(persona="startups") >= 1

    _run(go())


def test_chat_persona_switch_on_explicit_signal():
    """An explicit self-identification triggers a silent persona switch."""
    from app.main import app

    with TestClient(app) as client:
        # Personas are per-site now: HireBuddha's profile defines "startups";
        # an ad-hoc site like SITE has none (see test_agent_profile.py).
        r = client.post("/chat", json={
            "message": f"I'm a solo founder just getting started, ref {uuid.uuid4().hex}",
            "site": "hirebuddha",
        }).json()
        assert r["persona"] == "startups"  # mock infers from "founder"
        assert any(a.get("type") == "set_icp" for a in r["actions"])


def test_chat_replay_end_to_end():
    """Ask the same thing twice → the second response is served from cache."""
    from app.main import app

    q = "Cache replay probe " + uuid.uuid4().hex + "?"
    with TestClient(app) as client:
        # Only need one prior turn for this probe to qualify.
        app.state.runtime.settings.episodic_min_episodes = 1
        r1 = client.post("/chat", json={"message": q, "site": SITE}).json()
        assert r1["intent"] != "cached"
        r2 = client.post("/chat", json={"message": q, "site": SITE}).json()
        assert r2["intent"] == "cached"
        assert r2["text"] == r1["text"]
        # The replay carries the original answer's sources (WS8).
        assert r2["grounding"] == r1["grounding"]


def test_ws_replay_speaks_ack_before_cached_answer():
    """D-8: a cache hit sounds like a fresh turn — an ack_* segment, then the answer."""
    from app.main import app

    site = f"replayack-{uuid.uuid4().hex[:8]}"
    q = "Replay ack probe " + uuid.uuid4().hex + "?"

    async def seed():
        await init_db()
        settings = get_settings()
        async with session_scope() as db:
            cache = EpisodicCache(db, settings, build_cortex_providers(settings), site_key=site)
            await cache.record(question=q, answer_text="The cached answer.",
                               components=[], actions=[], persona=None, page="/",
                               channel="voice")
    _run(seed())

    with TestClient(app) as client:
        app.state.runtime.settings.episodic_min_episodes = 1
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text", "payload": {"text": q}})
            starts = []
            for _ in range(300):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "start":
                    starts.append((env["sync_id"], env["payload"].get("text", "")))
                    if len(starts) == 2:
                        break
            assert starts[0][0].startswith("ack_")
            assert starts[1][1] == "The cached answer."
