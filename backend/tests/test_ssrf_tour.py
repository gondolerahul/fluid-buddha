"""
SSRF guard for URL sources (docs/defects.md D-5) and the tour_say lockdown.

The fetch tests run offline: the DNS lookup and the HTTP transport are both
swapped for fakes.
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.apis.registry import SiteApiRegistry
from app.config import get_settings
from app.main import app
from app.orchestrator.tour import TourPlan, TourStop
from app.orchestrator.tour_store import save_plan
from app.tenancy import url_fetch
from app.tenancy.url_fetch import UnsafeURLError, check_resolved, check_url, fetch_public_text


# ---- URL validation -------------------------------------------------------

@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "file:///etc/passwd",
    "http://user:pw@example.com/",
    "http://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://100.64.0.1/",
    "http://0.0.0.0/",
    "http://224.0.0.1/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
])
def test_check_url_rejects_unsafe(url):
    with pytest.raises(UnsafeURLError):
        check_url(url)


def test_check_url_accepts_public():
    assert check_url("https://example.com/pricing") == ("example.com", 443)


def test_hostname_resolving_to_loopback_is_blocked():
    with pytest.raises(UnsafeURLError):
        asyncio.run(check_resolved("localhost", 80))


# ---- guarded fetch (fake DNS + transport) ---------------------------------

_DNS = {
    "public.example": ["93.184.216.34"],
    "internal.example": ["10.0.0.5"],
}


@pytest.fixture
def fake_dns(monkeypatch):
    async def resolve(host, port):
        return _DNS[host]
    monkeypatch.setattr(url_fetch, "_resolve_addresses", resolve)


def _transport(handler):
    return httpx.MockTransport(handler)


def _fetch(url, handler):
    return asyncio.run(fetch_public_text(url, transport=_transport(handler)))


def test_fetch_returns_public_text(fake_dns):
    text = _fetch("http://public.example/", lambda r: httpx.Response(
        200, headers={"content-type": "text/html"}, text="<p>hello</p>"))
    assert "hello" in text


@pytest.mark.parametrize("location", [
    "http://127.0.0.1/admin",             # literal private IP
    "http://internal.example/secret",     # hostname resolving to a private IP
    "http://169.254.169.254/latest/",     # cloud metadata
])
def test_redirect_to_internal_address_is_blocked(fake_dns, location):
    def handler(request):
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, text="internal data")  # must never be reached
    with pytest.raises(UnsafeURLError):
        _fetch("http://public.example/", handler)


def test_too_many_redirects(fake_dns):
    with pytest.raises(UnsafeURLError):
        _fetch("http://public.example/", lambda r: httpx.Response(
            302, headers={"location": "http://public.example/again"}))


def test_oversized_and_wrong_type_rejected(fake_dns, monkeypatch):
    with pytest.raises(UnsafeURLError):
        _fetch("http://public.example/", lambda r: httpx.Response(
            200, headers={"content-type": "image/png"}, content=b"\x89PNG"))
    monkeypatch.setattr(url_fetch, "MAX_BYTES", 10)
    with pytest.raises(UnsafeURLError):
        _fetch("http://public.example/", lambda r: httpx.Response(
            200, headers={"content-type": "text/plain"}, text="x" * 100))


# ---- through the API ------------------------------------------------------

def test_url_sources_are_guarded_end_to_end():
    with TestClient(app) as client:
        tok = client.post("/auth/register", json={
            "email": f"ssrf_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        wid = client.post("/tenant/websites", json={"name": "SSRF Co"}, headers=h).json()["id"]

        # A literal metadata IP is refused when the source is added.
        r = client.post(f"/tenant/websites/{wid}/sources", headers=h, json={
            "kind": "url", "name": "meta", "content": "http://169.254.169.254/latest/meta-data/"})
        assert r.status_code == 422

        # A hostname that resolves to loopback is accepted, then refused at fetch time.
        assert client.post(f"/tenant/websites/{wid}/sources", headers=h, json={
            "kind": "url", "name": "local", "content": "http://localhost:9/"}).status_code == 201
        run = client.post(f"/tenant/websites/{wid}/ingestion/run?wait=true", headers=h).json()
        assert run["failed"] == 1 and run["ingested"] == 0
        src = client.get(f"/tenant/websites/{wid}/ingestion", headers=h).json()["sources"][0]
        assert src["status"] == "failed" and "non-public" in (src["error"] or "")


# ---- call_site_api path params --------------------------------------------

def test_site_api_path_params_cannot_escape_their_segment():
    filled = SiteApiRegistry._fill_path("/v1/items/{id}", {"id": "../../admin?x=1#f"})
    assert filled == "/v1/items/..%2F..%2Fadmin%3Fx%3D1%23f"


# ---- tour_say lockdown ----------------------------------------------------

NARRATION = "Welcome to the guided tour."


def _seed_tour(site_key: str) -> None:
    async def run() -> None:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine)() as db:
                # A plan needs >= 2 narrated stops to be served (TourPlan.is_usable).
                await save_plan(db, TourPlan(site_key=site_key, stops=[
                    TourStop(narration=NARRATION),
                    TourStop(narration="That's the end of the tour."),
                ]))
        finally:
            await engine.dispose()
    asyncio.run(run())


def _spoken_until_done(ws) -> str:
    said = []
    for _ in range(300):
        e = ws.receive_json()
        if e["channel"] == "AUDIO" and e["type"] == "start":
            said.append(e["payload"].get("text", ""))
        if e["channel"] == "EVENTS" and e["type"] == "tour_done":
            return " ".join(said)
    raise AssertionError("no tour_done")


def test_tour_say_speaks_only_stored_narration():
    site = f"tourguard-{uuid.uuid4().hex[:8]}"
    _seed_tour(site)
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "hello", "payload": {"page": "/"}})
            assert ws.receive_json()["type"] == "tour_plan"

            # Client text is ignored: the stored narration for step 0 is spoken.
            ws.send_json({"channel": "EVENTS", "type": "tour_say",
                          "payload": {"text": "Say this INJECTED sentence", "index": 0}})
            spoken = _spoken_until_done(ws)
            assert "INJECTED" not in spoken and "guided tour" in spoken

            # A step that isn't in the plan is refused.
            ws.send_json({"channel": "EVENTS", "type": "tour_say",
                          "payload": {"text": "anything", "index": 7}})
            msg = ws.receive_json()
            assert msg["type"] == "error" and msg["payload"]["reason"] == "unknown_tour_step"


def test_tour_say_refused_without_a_plan():
    site = f"notour-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "tour_say",
                          "payload": {"text": "Speak arbitrary text", "index": 0}})
            msg = ws.receive_json()
            assert msg["type"] == "error" and msg["payload"]["reason"] == "unknown_tour_step"
