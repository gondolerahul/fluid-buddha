"""
Data lifecycle + public abuse guard tests.

- D-6: deleting a source removes the knowledge built from it; deleting a
  website purges its tree, tour, caches, usage and sources.
- D-3: the per-site rate limit and daily spend cap refuse public turns.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings, site_entity_id
from app.main import app
from app.transport import guard


def _scalar(sql: str, **params) -> int:
    """Run one count query on a throwaway engine (never the app's shared pool)."""
    async def run() -> int:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                return int((await conn.execute(text(sql), params)).scalar() or 0)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _site_with_ingested_source(client: TestClient) -> tuple[dict, dict, str]:
    tok = client.post("/auth/register", json={
        "email": f"lc_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    site = client.post("/tenant/websites", json={"name": f"Lifecycle {uuid.uuid4().hex[:6]}"},
                       headers=h).json()
    src = client.post(f"/tenant/websites/{site['id']}/sources", headers=h, json={
        "kind": "text", "name": "facts.md",
        "content": "# Facts\n\nOur widget answers questions about the zircon plan.",
    }).json()
    run = client.post(f"/tenant/websites/{site['id']}/ingestion/run?wait=true", headers=h).json()
    assert run["ingested"] == 1 and run["nodes"] > 0
    return h, site, src["id"]


_NODES_FOR_DOC = (
    "SELECT count(*) FROM cortex_nodes WHERE source_ref->>'document_id' = :doc"
)


def test_delete_source_removes_its_knowledge():
    with TestClient(app) as client:
        h, site, sid = _site_with_ingested_source(client)
        assert _scalar(_NODES_FOR_DOC, doc=sid) > 0

        assert client.delete(f"/tenant/websites/{site['id']}/sources/{sid}",
                             headers=h).status_code == 204
        assert _scalar(_NODES_FOR_DOC, doc=sid) == 0


def test_delete_website_purges_everything():
    with TestClient(app) as client:
        h, site, sid = _site_with_ingested_source(client)
        sk = site["site_key"]
        # A public turn records usage (and a cache entry) for the site.
        assert client.post("/chat", json={"message": "what plan?",
                                          "key": site["public_key"]}).status_code == 200
        assert _scalar("SELECT count(*) FROM usage_events WHERE site_key = :sk", sk=sk) > 0

        assert client.delete(f"/tenant/websites/{site['id']}", headers=h).status_code == 204

        assert _scalar("SELECT count(*) FROM cortex_trees WHERE entity_id = :e",
                       e=site_entity_id(sk)) == 0
        assert _scalar(_NODES_FOR_DOC, doc=sid) == 0
        for table in ("usage_events", "conversation_cache", "site_tours"):
            assert _scalar(f"SELECT count(*) FROM {table} WHERE site_key = :sk", sk=sk) == 0
        assert _scalar("SELECT count(*) FROM tenant_sources WHERE id = :id", id=sid) == 0


def test_rate_limit_refuses_excess_turns(monkeypatch):
    # Own limiter with a long window: isolated state, and no minute boundary
    # can reset the count mid-test.
    monkeypatch.setattr(guard, "_limiter", guard.RateLimiter(window_s=3600))
    site = f"ratetest-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        app.state.runtime.settings.public_rate_limit_per_min = 2
        codes = [client.post("/chat", json={"message": f"q{i}", "site": site}).status_code
                 for i in range(3)]
        assert codes[:2] == [200, 200]
        assert codes[2] == 429
        r = client.post("/chat", json={"message": "again", "site": site})
        assert r.json()["detail"] == guard.RATE_LIMITED


def test_daily_spend_cap_refuses_once_reached():
    site = f"spendtest-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        app.state.runtime.settings.public_daily_spend_cap_usd = 1e-9
        # Nothing spent yet: allowed, and this turn records a non-zero cost.
        assert client.post("/chat", json={"message": "hello", "site": site}).status_code == 200
        r = client.post("/chat", json={"message": "hello again", "site": site})
        assert r.status_code == 429 and r.json()["detail"] == guard.SPEND_CAP_REACHED


def test_ws_turn_refused_when_rate_limited(monkeypatch):
    monkeypatch.setattr(guard, "_limiter", guard.RateLimiter(window_s=3600))
    site = f"wsrate-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        app.state.runtime.settings.public_rate_limit_per_min = 1
        guard._limiter.allow(site, 1)  # use up this minute's only turn
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text", "payload": {"text": "hi"}})
            msg = ws.receive_json()
            assert msg["channel"] == "EVENTS" and msg["type"] == "error"
            assert msg["payload"]["reason"] == guard.RATE_LIMITED


# ---- D-10: re-ingestion never clobbers a hand-edited tour ---------------------

def _auto_replan(site_key: str, narration: str) -> bool:
    """What re-ingestion does: save a generated plan, keeping hand edits."""
    from app.orchestrator.tour import TourPlan, TourStop
    from app.orchestrator.tour_store import save_plan

    async def run() -> bool:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                return await save_plan(db, TourPlan(site_key=site_key, stops=[
                    TourStop(narration=narration), TourStop(narration="The end."),
                ]), keep_edited=True)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_reingestion_keeps_hand_edited_tour():
    with TestClient(app) as client:
        tok = client.post("/auth/register", json={
            "email": f"lt_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        site = client.post("/tenant/websites", json={"name": "Tour Co"}, headers=h).json()
        url = f"/tenant/websites/{site['id']}/tour"

        # Before any hand edit, a re-plan is written.
        assert _auto_replan(site["site_key"], "Generated intro.") is True
        assert client.get(url, headers=h).json()["edited"] is False

        stops = [{"narration": "My own intro."}, {"narration": "My own outro."}]
        saved = client.put(url, json={"stops": stops}, headers=h).json()
        assert saved["edited"] is True

        # A later re-ingestion leaves the hand-edited tour untouched.
        assert _auto_replan(site["site_key"], "Generated again.") is False
        tour = client.get(url, headers=h).json()
        assert tour["edited"] is True
        assert [s["narration"] for s in tour["stops"]] == ["My own intro.", "My own outro."]
