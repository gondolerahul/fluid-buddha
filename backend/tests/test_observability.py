"""
Production plumbing (F-3): request ids, Prometheus metrics, time to first
audio, tracing spans, Sentry scrubbing, and shared state (sessions and the
rate limit) in Redis.

The Redis tests use ``TEST_REDIS_URL`` (default ``redis://localhost:6380/15``)
and are skipped when nothing answers there.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.main import app
from app.observability import metrics as prom
from app.observability.context import ContextFilter, JsonFormatter, new_request_id, request_id
from app.observability.errors import scrub
from app.orchestrator.state import ConversationState
from app.transport.session_store import MemorySessionStore, RedisSessionStore, SessionStore

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/15")


def _db(sql: str, **params):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(sql), params)).mappings().all()
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _sample(name: str, **labels) -> float:
    return prom.REGISTRY.get_sample_value(name, labels) or 0.0


# ---- request ids and logs ------------------------------------------------------

def test_request_id_is_echoed_or_made():
    with TestClient(app) as client:
        assert client.get("/healthz", headers={"X-Request-ID": "trace-42"}).headers["x-request-id"] == "trace-42"
        # An id that could forge log lines is replaced.
        bad = client.get("/healthz", headers={"X-Request-ID": "x\r\nFAKE LOG"}).headers["x-request-id"]
        assert len(bad) == 32 and "\n" not in bad
        assert len(client.get("/healthz").headers["x-request-id"]) == 32
    assert new_request_id("a" * 65) != "a" * 65


def test_log_lines_carry_the_request_id(caplog):
    caplog.handler.addFilter(ContextFilter())
    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        client.post("/chat", headers={"X-Request-ID": "log-probe-7"},
                    json={"message": "hello there", "site": "hirebuddha"})
    tagged = [r for r in caplog.records if getattr(r, "request_id", None) == "log-probe-7"]
    assert tagged, "no log line carried the request id"

    token = request_id.set("json-probe")
    try:
        rec = logging.LogRecord("a2ui", logging.INFO, __file__, 1, "hi %s", ("there",), None)
        ContextFilter().filter(rec)
        line = JsonFormatter().format(rec)
    finally:
        request_id.reset(token)
    import json
    data = json.loads(line)
    assert data["msg"] == "hi there" and data["request_id"] == "json-probe"


# ---- metrics --------------------------------------------------------------------

def test_metrics_endpoint_uses_route_templates_and_can_be_guarded():
    settings = get_settings()
    with TestClient(app) as client:
        client.get(f"/tenant/websites/{uuid.uuid4()}/experiment")  # 401, but templated
        body = client.get("/metrics").text
        assert 'route="/tenant/websites/{website_id}/experiment"' in body
        assert "fb_time_to_first_audio_seconds" in body
        assert "/tenant/websites/" + "0" not in body  # no ids leak into labels

        settings.metrics_token = "s3cret-scrape"   # restored by conftest
        assert client.get("/metrics").status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/metrics", headers={"Authorization": "Bearer s3cret-scrape"}).status_code == 200
        settings.metrics_enabled = False
        assert client.get("/metrics").status_code == 404


# ---- time to first audio ---------------------------------------------------------

def test_voice_turn_records_time_to_first_audio():
    before = _sample("fb_time_to_first_audio_seconds_count", path="fresh")
    before_answer = _sample("fb_time_to_first_answer_audio_seconds_count", path="fresh")
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
            ready = ws.receive_json()
            session = ready["payload"]["session_id"]
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "How do you integrate with our API?"}})
            ends = 0
            for _ in range(400):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                    if ends >= 2:
                        break
        row = None
        for _ in range(50):  # usage is recorded in the background
            rows = _db("SELECT ttfa_ms, latency_ms FROM usage_events WHERE session_id = :s", s=session)
            if rows:
                row = rows[0]
                break
            time.sleep(0.1)
        assert row is not None
        assert row["ttfa_ms"] is not None and 0 < row["ttfa_ms"] <= row["latency_ms"]
        assert _sample("fb_time_to_first_audio_seconds_count", path="fresh") == before + 1
        assert _sample("fb_time_to_first_answer_audio_seconds_count", path="fresh") == before_answer + 1
        assert _sample("fb_turns_total", channel="voice", path="fresh") >= 1
        assert _sample("fb_stage_seconds_count", stage="route") >= 1
        assert _sample("fb_stage_seconds_count", stage="tts") >= 1


def test_analytics_reports_ttfa_percentiles():
    from app.analytics.usage import TurnMetrics, analytics, record_turn

    site = f"ttfa-{uuid.uuid4().hex[:8]}"

    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        from sqlalchemy.ext.asyncio import AsyncSession
        try:
            async with AsyncSession(engine) as db:
                for ms in (400, 600, 800, 1000):
                    await record_turn(db, TurnMetrics(site_key=site, channel="voice",
                                                      latency_ms=3000, ttfa_ms=ms))
                await record_turn(db, TurnMetrics(site_key=site, channel="text", latency_ms=900))
                return await analytics(db, site_key=site)
        finally:
            await engine.dispose()
    perf = asyncio.run(go())["performance"]
    assert perf["ttfa_turns"] == 4
    assert perf["p50_ttfa_ms"] == pytest.approx(700.0)
    assert perf["p95_ttfa_ms"] == pytest.approx(970.0)


# ---- tracing ---------------------------------------------------------------------

def test_turns_are_traced_when_a_collector_is_configured():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from app.observability.tracing import disable_tracing, setup_tracing

    exporter = InMemorySpanExporter()
    assert setup_tracing(get_settings(), exporter=exporter)
    try:
        with TestClient(app) as client:
            client.post("/chat", json={"message": "How does pricing work?", "site": "hirebuddha"})
    finally:
        disable_tracing()
    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert {"http.request", "chat.turn", "stage.retrieval"} <= set(spans)
    http = spans["http.request"]
    assert http.attributes["http.route"] == "/chat"
    # Stages are children of the turn, the turn of the request.
    assert spans["chat.turn"].parent.span_id == http.context.span_id
    # Nothing the visitor typed is recorded.
    for s in exporter.get_finished_spans():
        assert not any("pricing" in str(v).lower() for v in s.attributes.values())


# ---- Sentry --------------------------------------------------------------------------

def test_sentry_events_are_scrubbed():
    event = {
        "request": {"url": "https://api.example/chat", "data": '{"message":"my email is jo@acme.io"}',
                    "cookies": {"s": "1"}, "query_string": "key=abc",
                    "headers": {"Authorization": "Bearer t", "User-Agent": "ua", "Cookie": "s=1"}},
        "user": {"ip_address": "1.2.3.4"},
        "exception": {"values": [{"stacktrace": {"frames": [{"function": "f", "vars": {"text": "secret"}}]}}]},
        "breadcrumbs": {"values": [{"message": "q", "data": {"body": "secret"}}]},
    }
    token = request_id.set("sentry-probe")
    try:
        out = scrub(event)
    finally:
        request_id.reset(token)
    assert "data" not in out["request"] and "cookies" not in out["request"]
    assert "query_string" not in out["request"]
    assert out["request"]["headers"] == {"User-Agent": "ua"}
    assert "user" not in out
    assert "vars" not in out["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert "data" not in out["breadcrumbs"]["values"][0]
    assert out["tags"]["request_id"] == "sentry-probe"


def test_sentry_reports_through_the_scrubber():
    import sentry_sdk
    from sentry_sdk.transport import Transport

    from app.observability.errors import setup_sentry

    sent = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            sent.extend(item.payload.json for item in envelope.items
                        if item.payload.json is not None)

    settings = get_settings()
    settings.sentry_dsn = "https://public@sentry.example/1"   # restored by conftest
    assert setup_sentry(settings, transport=Capture)
    try:
        token = request_id.set("err-probe")
        try:
            try:
                # Built at runtime: Sentry sends source lines, so a literal would
                # show up as code, not as a leaked variable.
                transcript = "my card is " + " ".join(["41" + "11"] * 4)  # noqa: F841
                raise RuntimeError("thinker blew up")
            except RuntimeError:
                sentry_sdk.capture_exception()
        finally:
            request_id.reset(token)
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # no DSN: reporting off again
    events = [e for e in sent if e.get("exception")]
    assert events and events[0]["tags"]["request_id"] == "err-probe"
    assert "4111 1111" not in str(events[0])  # the local variable was dropped


# ---- sessions --------------------------------------------------------------------------

def test_state_round_trips_with_its_pii_placeholders():
    s = ConversationState(site_key="acme", persona="retailers", page="/pricing")
    masked = s.pii.mask("reach me at jo@acme.io")
    s.add_turn(masked, "Thanks!")
    s.register_component("ui_1", "chart", {"data": [1, 2]})
    back = ConversationState.from_dict(__import__("json").loads(__import__("json").dumps(s.to_dict())))
    assert back.persona == "retailers" and back.page == "/pricing"
    assert back.history[0].text == masked and back.components["ui_1"]["component_type"] == "chart"
    # A later turn can still hand the real address to capture_lead.
    assert back.pii.unmask(masked) == "reach me at jo@acme.io"
    assert back.pii.mask("jo@acme.io again") == masked.replace("reach me at ", "") + " again"


def test_memory_store_expires_caps_and_keeps_sites_apart():
    async def go():
        backend = MemorySessionStore(ttl_s=60, max_sessions=2)
        store = SessionStore(backend)
        sid, st = await store.load(None, site_key="a")
        st.add_turn("q", "a")
        await store.save(sid, st)
        assert (await store.load(sid, site_key="a"))[1].history          # same site: resumed
        other_sid, other = await store.load(sid, site_key="b")            # another site: fresh
        assert other_sid != sid and not other.history
        for i in range(3):
            await store.save(f"s{i}", ConversationState(site_key="a"))
        assert await backend.get(sid) is None and len(backend._states) == 2  # capped
        backend.ttl_s = 0
        await asyncio.sleep(0.01)
        assert await backend.get("s2") is None                           # idle: expired
    asyncio.run(go())


def _redis_or_skip():
    import redis.asyncio as redis

    async def ping():
        c = redis.from_url(TEST_REDIS_URL, decode_responses=True, socket_connect_timeout=0.5)
        try:
            await c.ping()
            return True
        except Exception:
            return False
        finally:
            await c.aclose()
    if not asyncio.run(ping()):
        pytest.skip(f"no Redis at {TEST_REDIS_URL}")


def test_redis_session_store_shares_state_between_replicas():
    _redis_or_skip()
    import redis.asyncio as redis

    async def go():
        a = redis.from_url(TEST_REDIS_URL, decode_responses=True)
        b = redis.from_url(TEST_REDIS_URL, decode_responses=True)  # "another replica"
        try:
            one, two = SessionStore(RedisSessionStore(a, 60)), SessionStore(RedisSessionStore(b, 60))
            sid, st = await one.load(None, site_key="acme")
            st.add_turn(st.pii.mask("call me on +1 415 555 0100"), "Will do.")
            await one.save(sid, st)
            sid2, again = await two.load(sid, site_key="acme")
            assert sid2 == sid and len(again.history) == 2
            assert "555" in again.pii.unmask(again.history[0].text)
            assert 0 < await b.ttl("fb:chat:" + sid) <= 60
            assert (await two.load(sid, site_key="other"))[0] != sid
            await two.drop(sid)
            assert (await one.load(sid, site_key="acme"))[0] != sid
        finally:
            await a.aclose()
            await b.aclose()
    asyncio.run(go())


def test_rate_limit_window_is_shared_through_redis(monkeypatch):
    _redis_or_skip()
    import redis.asyncio as redis

    from app import shared_state
    from app.transport import guard

    async def go():
        client = redis.from_url(TEST_REDIS_URL, decode_responses=True)
        monkeypatch.setattr(shared_state, "redis_client", lambda: client)
        site = f"rl-{uuid.uuid4().hex[:8]}"
        try:
            results = [await guard._allow(site, 3) for _ in range(5)]
            # Counted in Redis, not in this process.
            assert not guard._limiter._windows.get(site)
            return results
        finally:
            await client.aclose()
    assert asyncio.run(go()) == [True, True, True, False, False]


def test_rate_limit_falls_back_in_process_when_redis_is_down(monkeypatch):
    from app import shared_state
    from app.transport import guard

    class Down:
        async def incr(self, key):
            raise ConnectionError("redis down")

    monkeypatch.setattr(shared_state, "redis_client", lambda: Down())
    site = f"rl-{uuid.uuid4().hex[:8]}"
    assert asyncio.run(guard._allow(site, 1)) is True
    assert asyncio.run(guard._allow(site, 1)) is False
