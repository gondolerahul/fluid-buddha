"""
Reliability for the 99.9 % SLA (M3-6): readiness of every dependency (503
when a critical one fails or the replica drains), graceful drain of voice
sessions (move, finish the answer, 1012; new sockets 1013), the status page
(probe, components, uptime, incidents posted by operators), the fb_ready
gauge, alert rules that only use metrics the app exports, and the voice load
test running against a real server.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import threading
import time
import uuid
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.main import app
from app.observability import health
from app.transport import drain

ROOT = Path(__file__).resolve().parents[2]


def test_readiness_checks_every_dependency(monkeypatch):
    with TestClient(app) as client:
        r = client.get("/readyz")
        body = r.json()
        assert r.status_code == 200 and body["status"] in ("ok", "degraded"), body
        assert set(body["checks"]) == {"db", "migrations", "redis", "scheduler", "models", "email", "draining"}
        assert body["checks"]["db"]["ok"] and body["checks"]["migrations"]["ok"] and body["db"] is True
        assert all("ms" in c for c in body["checks"].values())

        async def broken():
            raise ConnectionError("connection refused")
        monkeypatch.setattr(health, "_db", broken)
        r = client.get("/readyz")
        assert r.status_code == 503 and r.json()["status"] == "fail"
        assert "ConnectionError" in r.json()["checks"]["db"]["detail"]
        monkeypatch.undo()

        monkeypatch.setattr(health, "head_revision", lambda: "9999_future")
        r = client.get("/readyz")
        assert r.status_code == 503 and "expected 9999_future" in r.json()["checks"]["migrations"]["detail"]
        monkeypatch.undo()

        # A non-critical failure is reported, but the replica still serves.
        async def no_email():
            return {"ok": False, "detail": "120 emails waiting over 15 minutes"}
        monkeypatch.setattr(health, "_email", no_email)
        r = client.get("/readyz")
        assert r.status_code == 200 and r.json()["status"] == "degraded"
        monkeypatch.undo()

        metrics = client.get("/metrics").text
        assert 'fb_ready{check="db"} 1.0' in metrics and "fb_draining" in metrics


def test_a_draining_replica_moves_its_voice_sessions():
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
                assert ws.receive_json()["type"] == "ready"
                result = client.portal.call(drain.drain, 2.0)
                assert result["sessions"] >= 1 and result["forced"] == 0
                env = ws.receive_json()
                assert env["channel"] == "EVENTS" and env["type"] == "reconnect"
                with pytest.raises(WebSocketDisconnect) as closed:
                    while True:
                        ws.receive_json()
                assert closed.value.code == drain.SERVICE_RESTART
            r = client.get("/readyz")
            assert r.status_code == 503 and r.json()["status"] == "draining"
            assert 'fb_draining 1.0' in client.get("/metrics").text
            # New sockets are sent elsewhere.
            with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
                assert ws.receive_json()["type"] == "reconnect"
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
                assert closed.value.code == drain.TRY_AGAIN_LATER
        finally:
            drain.reset()
        assert client.get("/readyz").status_code == 200


def test_an_answer_being_spoken_finishes_before_the_close():
    async def run():
        quick = asyncio.create_task(asyncio.sleep(0.05))
        assert await drain.wait_for_turn(quick, 1.0) is False and quick.done()
        slow = asyncio.create_task(asyncio.sleep(5))
        assert await drain.wait_for_turn(slow, 0.05) is True
        slow.cancel()
        assert await drain.wait_for_turn(None, 1.0) is False
    asyncio.run(run())


def test_status_page_probe_components_and_incidents():
    s = get_settings()
    before = s.status_token
    token = f"st_{uuid.uuid4().hex}"
    try:
        with TestClient(app) as client:
            from app.db import session_scope
            from app.status import store

            async def probe():
                async with session_scope() as db:
                    return await store.probe(db, app)
            states = client.portal.call(probe)
            assert set(states) == {"api", "voice", "jobs", "email"} and states["api"][0] == "up"

            j = client.get("/status.json").json()
            assert j["overall"] in ("operational", "degraded") and len(j["components"]) == 4
            api = next(c for c in j["components"] if c["key"] == "api")
            assert api["state"] == "up" and len(api["days"]) == 90 and api["days"][-1]["state"] == "up"
            assert api["uptime"] is not None and api["uptime"] > 0
            html = client.get("/status")
            assert html.status_code == 200 and "API, widget and console" in html.text
            assert "script" not in html.text.lower() and "default-src 'none'" in html.headers["content-security-policy"]

            # Posting needs the operator token.
            s.status_token = ""
            assert client.post("/status/incidents", json={"title": "x", "body": "y"}).status_code == 404
            s.status_token = token
            assert client.post("/status/incidents", json={"title": "x", "body": "y"},
                               headers={"Authorization": "Bearer wrong"}).status_code == 401
            h = {"Authorization": f"Bearer {token}"}
            assert client.post("/status/incidents", headers=h, json={"title": "x", "impact": "huge",
                                                                       "body": "y"}).status_code == 422
            inc = client.post("/status/incidents", headers=h, json={
                "title": f"Voice answers are slow {uuid.uuid4().hex[:4]}", "impact": "critical",
                "components": ["voice", "nonsense"], "body": "We're looking into slow voice answers."}).json()
            assert inc["status"] == "investigating" and inc["components"] == ["voice"]
            j = client.get("/status.json").json()
            assert next(c for c in j["components"] if c["key"] == "voice")["state"] == "down"
            assert j["overall"] == "outage" and "Voice answers are slow" in client.get("/status").text
            done = client.post(f"/status/incidents/{inc['id']}/updates", headers=h,
                               json={"status": "resolved", "body": "Fixed: a slow model region."}).json()
            assert done["status"] == "resolved" and done["resolved_at"] and len(done["updates"]) == 2
            j = client.get("/status.json").json()
            assert next(c for c in j["components"] if c["key"] == "voice")["state"] == "up"
            assert any(i["id"] == inc["id"] and i["status"] == "resolved" for i in j["incidents"])
            assert client.post(f"/status/incidents/{uuid.uuid4()}/updates", headers=h,
                               json={"status": "resolved", "body": "?"}).status_code == 404
    finally:
        s.status_token = before
        _sql_delete_test_incidents()


def _sql_delete_test_incidents():
    async def run():
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                await db.execute(text("DELETE FROM status_incidents WHERE title LIKE 'Voice answers are slow %'"))
                await db.commit()
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_components_follow_the_checks():
    from app.status.store import components_from
    ok = {n: {"ok": True} for n in ("db", "migrations", "redis", "scheduler", "models", "email")}
    assert all(st == "up" for st, _ in components_from(ok).values())
    states = components_from({**ok, "models": {"ok": False, "detail": "quota"}})
    assert states["voice"] == ("degraded", "models: quota") and states["api"][0] == "up"
    states = components_from({**ok, "db": {"ok": False, "detail": "refused"}})
    assert states["api"][0] == "down" and states["voice"][0] == "down" and states["jobs"][0] == "up"


def test_alert_rules_only_use_metrics_the_app_exports():
    from app.observability.metrics import REGISTRY

    exported = set()
    for m in REGISTRY.collect():
        exported.add(m.name)
        for s in m.samples:
            exported.add(s.name)
    for name in list(exported):
        exported |= {name + "_total", name + "_bucket", name + "_count", name + "_sum"}
    rules = yaml.safe_load((ROOT / "deploy" / "monitoring" / "alerts.yml").read_text(encoding="utf-8"))
    alerts = [r for g in rules["groups"] for r in g["rules"] if "alert" in r]
    assert len(alerts) >= 10
    recorded = {r["record"] for g in rules["groups"] for r in g["rules"] if "record" in r}
    for g in rules["groups"]:
        for r in g["rules"]:
            for metric in re.findall(r"\b(fb_[a-z_]+)", r["expr"]):
                assert metric in exported, f"{r.get('alert') or r.get('record')} uses unknown {metric}"
    runbook = (ROOT / "docs" / "operations" / "incident-runbook.md").read_text(encoding="utf-8")
    # GitHub's heading anchors: lower case, punctuation dropped, spaces to dashes.
    slugs = {re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", h.strip().lower()))
             for h in re.findall(r"^#+\s+(.+)$", runbook, re.M)}
    for a in alerts:
        assert a["labels"]["severity"] in ("page", "ticket"), a["alert"]
        anchor = a["annotations"]["runbook"].split("#")[1]
        assert anchor in slugs, f"{a['alert']}: runbook section #{anchor} missing"
    assert recorded >= {"fb:http_error_ratio:rate5m", "fb:http_error_ratio:rate1h"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_voice_load_test_against_a_real_server():
    import uvicorn

    from loadtest import voice

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        assert server.started
        out = asyncio.run(voice.run(f"ws://127.0.0.1:{port}/ws/voice?site=hirebuddha&audio=binary",
                                    sessions=8, turns=2, ramp=0.5, think=0.0, timeout=20))
        assert out["connect_failed"] == 0 and out["turns_failed"] == 0, out["errors"]
        assert out["turns"] == 16 and out["time_to_first_audio_s"]["p95"] is not None
        assert out["time_to_first_audio_s"]["p95"] < 5 and out["turn_s"]["n"] == 16
    finally:
        server.should_exit = True
        thread.join(timeout=10)
