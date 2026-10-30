"""
Backend tests (mock mode). Requires the pgvector container up and the site
ingested:  docker compose up -d  &&  python -m ingestion.ingest --site hirebuddha
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.transport.envelope import Channel, make


# ---- pure unit tests ------------------------------------------------------

def test_envelope_shape():
    env = make(Channel.AUDIO, "chunk", {"data": "abc"}, sync_id="ui_1")
    assert env["channel"] == "AUDIO"
    assert env["type"] == "chunk"
    assert env["payload"] == {"data": "abc"}
    assert env["sync_id"] == "ui_1"
    assert isinstance(env["timestamp"], int)


def test_tools_gated_by_intelligence_level():
    from app.orchestrator.tools import tools_for

    names = lambda lvl, site=None: {t.name for t in tools_for(lvl, site)}
    assert names("basic") == {"query_cortex", "navigate", "scroll_to"}
    assert "set_persona" in names("high")
    assert "render_component" not in names("high")
    assert "render_component" in names("advance")
    assert "generate_page" in names("extreme")
    # Unknown level falls back to the advance set.
    assert names("garbage") == names("advance")


def test_normalize_intelligence():
    from app.orchestrator.state import normalize_intelligence

    assert normalize_intelligence("Extreme") == "extreme"
    assert normalize_intelligence("bogus") == "advance"
    assert normalize_intelligence(None) == "advance"


def test_design_system_endpoint_returns_tokens():
    import asyncio

    from app.routes.design import design_system

    doc = asyncio.run(design_system(site="fluidbuddha"))
    assert "tokens" in doc and doc["tokens"]["--ds-color-primary"]
    assert doc["brand_voice"]
    assert "--ds-radius" in doc["tokens"]


def test_normalize_page_drops_unknown_sections():
    from app.orchestrator.pagegen import normalize_page

    title, sections = normalize_page("Hi", [
        {"type": "hero", "props": {"title": "H"}},
        {"type": "bogus"},
        {"type": "text", "props": {"body": "b"}},
        "junk",
    ])
    assert title == "Hi"
    assert [s["type"] for s in sections] == ["hero", "text"]


def test_site_api_registry_simulates_and_rejects_unknown():
    import asyncio

    from app.apis.registry import SiteApiRegistry

    spec = {"paths": {"/enquiry": {"post": {"operationId": "submit_enquiry",
                                            "summary": "Submit"}}}}
    reg = SiteApiRegistry("demo", spec, base_url="", auth="")
    assert [o.operation_id for o in reg.operations()] == ["submit_enquiry"]
    ok = asyncio.run(reg.call("submit_enquiry", {"email": "a@b.c"}))
    assert ok["ok"] and ok["simulated"]
    bad = asyncio.run(reg.call("nope", {}))
    assert bad["error"] == "unknown_operation"


def test_extreme_thinker_generates_grounded_page():
    import asyncio

    from app.ai.mock import MockLLMClient
    from app.config import get_settings
    from app.orchestrator.thinker import HeavyThinker

    class StubBridge:
        site_key = "fluidbuddha"

        async def search(self, query, top_k=5):
            return [{"content": "Fluid Buddha builds calm, voice-first sites.",
                     "score": 0.72, "document_title": "about", "section_title": "About"}]

    th = HeavyThinker(MockLLMClient(), get_settings())
    res = asyncio.run(th.think(
        user_text="show me your pricing", persona=None, bridge=StubBridge(),
        site_key="fluidbuddha", intelligence="extreme",
    ))
    assert res.grounding.found
    assert len(res.pages) == 1
    assert res.pages[0].sections  # has typed sections

    # The advance tier must NOT generate pages (capability gating).
    res2 = asyncio.run(th.think(
        user_text="how do you integrate?", persona=None, bridge=StubBridge(),
        site_key="fluidbuddha", intelligence="advance",
    ))
    assert res2.pages == []


def test_query_cortex_guardrail_low_confidence():
    """Below-threshold retrieval must set found=false and attach a guardrail."""
    from app.cortex.query import query_cortex

    class StubBridge:
        site_key = "hirebuddha"

        async def search(self, query, top_k=5):
            return [{"content": "weak match", "score": 0.10,
                     "document_title": "d", "section_title": "s"}]

    res = asyncio.run(query_cortex(StubBridge(), "anything", threshold=0.45))
    assert res["found"] is False
    assert "guardrail" in res
    assert res["confidence"] == 0.10


# ---- integration tests (DB + cognitive loop) ------------------------------

def test_chat_turn_returns_message_shape():
    with TestClient(app) as client:
        r = client.post("/chat", json={
            "message": "How does pricing work for a growing company?"
        }).json()
        for key in ("text", "ack", "intent", "persona", "actions",
                    "components", "grounding", "session_id"):
            assert key in r, f"missing {key}"
        assert isinstance(r["actions"], list)
        assert isinstance(r["components"], list)


def test_ws_voice_turn_streams_synced_audio():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "How do you integrate with our API?"}})
            audio_starts, ends = [], 0
            for _ in range(300):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "start":
                    audio_starts.append(env["sync_id"])
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                    if ends >= 2:
                        break
            # ack + answer = at least two distinct spoken segments
            assert len(audio_starts) >= 2


def test_ws_live_reaction_to_component_interaction():
    """Playing with a rendered component triggers a short spoken reaction."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "show me the roi for my team"}})
            # Drain the turn: capture the rendered component + its spoken answer.
            sync_id, ends = None, 0
            for _ in range(400):
                env = ws.receive_json()
                if env["channel"] == "DATA" and env["type"] == "render":
                    sync_id = env["payload"]["sync_id"]
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                if sync_id and ends >= 2:
                    break
            assert sync_id, "agent should have rendered a component"

            # The visitor drags a slider → report the new component state.
            ws.send_json({"channel": "STATE", "type": "sync", "payload": {
                "component_state": {"sync_id": sync_id, "values": {"seats": 50}}}})

            # After the debounce, a spoken reaction arrives on a react_* sync id.
            reacted = False
            for _ in range(400):
                env = ws.receive_json()
                if (env["channel"] == "AUDIO" and env["type"] == "start"
                        and str(env.get("sync_id", "")).startswith("react_")):
                    assert env["payload"].get("text")
                    reacted = True
                    break
            assert reacted, "expected a live spoken reaction to the interaction"


def test_split_for_tts_chunks_sentences():
    from app.transport.websocket import split_for_tts

    chunks = split_for_tts(
        "HireBuddha automates hiring. It screens candidates and books interviews. "
        "You save hours every week."
    )
    assert len(chunks) >= 3  # first audio after one sentence, not the whole answer
    assert chunks[0].startswith("HireBuddha")
    assert split_for_tts("") == []


def test_hybrid_needs_heavy_routing():
    from app.orchestrator.loop import CognitiveLoop

    nh = CognitiveLoop.needs_heavy
    # plain conversation → lean
    assert nh("hi there") is False
    assert nh("what does your company do?") is False
    # visuals / navigation / numbers → heavy
    assert nh("show me a diagram of the hiring workflow") is True
    assert nh("take me to the pricing page") is True
    assert nh("can you compare the plans?") is True
    assert nh("anything at all", intent="pricing_roi") is True


def test_ws_tour_plan_and_say():
    """hello → tour_plan (when authored); tour_say → spoken narration + tour_done."""
    from app.db import SessionLocal
    from app.orchestrator.tour import TourPlan, TourStop
    from app.orchestrator.tour_store import save_plan

    async def seed() -> None:
        from app.db import dispose_engine
        async with SessionLocal() as db:
            await save_plan(db, TourPlan(site_key="tourtest", stops=[
                TourStop(narration="Welcome — let me show you around.",
                         move={"type": "scroll", "target": "down"}),
                TourStop(narration="And that's the highlights. Here's what it means for you."),
            ]))
        # Release pool connections bound to this throwaway loop so the TestClient
        # (which runs on its own loop) gets fresh ones.
        await dispose_engine()

    asyncio.run(seed())

    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=tourtest") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "hello", "payload": {"page": "/"}})
            plan_env = ws.receive_json()
            assert plan_env["channel"] == "EVENTS" and plan_env["type"] == "tour_plan"
            assert len(plan_env["payload"]["stops"]) == 2

            ws.send_json({"channel": "EVENTS", "type": "tour_say",
                          "payload": {"text": "Welcome — let me show you around.", "index": 0}})
            saw_audio = saw_done = False
            for _ in range(200):
                e = ws.receive_json()
                if e["channel"] == "AUDIO" and e["type"] == "start":
                    saw_audio = True
                if e["channel"] == "EVENTS" and e["type"] == "tour_done":
                    assert e["payload"]["index"] == 0
                    saw_done = True
                    break
            assert saw_audio and saw_done
