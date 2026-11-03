"""
Lead capture (WS7): the enquiry form posts straight to /leads (no LLM), the
agent's capture_lead tool saves leads mid-conversation, every lead is scored
and summarised, and delivery is a signed webhook plus a Slack alert when hot.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import dispose_engine
from app.leads import delivery
from app.leads.store import LeadIn, score_lead, summarize
from app.main import app


def _tenant_site(client: TestClient, name: str = "Lead Co") -> tuple[dict, dict]:
    tok = client.post("/auth/register", json={
        "email": f"ld_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    return h, client.post("/tenant/websites", json={"name": name}, headers=h).json()


def test_score_and_summary_are_transparent():
    bare = LeadIn(email="a@b.co").cleaned()
    assert score_lead(bare, [], None) == 20
    rich = LeadIn(email="a@b.co", name="Ana", company="Acme").cleaned()
    qs = ["What does pricing look like?", "Do you have an API?"]
    assert score_lead(rich, qs, "startups") == 20 + 20 + 20 + 10 + 15
    assert summarize(rich, qs) == ("Asked 2 questions: What does pricing look like?; "
                                   "Do you have an API?")


def test_form_lead_is_stored_without_the_llm():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        key = site["public_key"]
        r = client.post("/leads", json={"key": key, "values": {
            "Name": "Ana Diaz", "Email": "ANA@Acme.io", "company": "Acme",
            "message": "Need a demo", "budget": "10k"}})
        assert r.status_code == 201
        leads = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()
        assert leads["total"] == 1
        lead = leads["items"][0]
        assert (lead["email"], lead["name"], lead["source"]) == ("ana@acme.io", "Ana Diaz", "form")
        assert lead["message"] == "Need a demo\nbudget: 10k"
        assert lead["score"] == 20 + 20 + 15   # email, name + company, "demo"

        assert client.post("/leads", json={"key": key, "email": "nope"}).status_code == 422
        assert client.post("/leads", json={"key": "fbk_bogus", "email": "a@b.co"}).status_code == 403
        # A registered tenant site can't be reached without its key.
        assert client.post("/leads", json={"site": site["site_key"],
                                           "email": "a@b.co"}).status_code == 403
        lid = lead["id"]
        assert client.patch(f"/tenant/websites/{site['id']}/leads/{lid}", headers=h,
                            json={"status": "contacted"}).json()["status"] == "contacted"


def test_agent_captures_a_lead_mid_conversation():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        app.state.runtime.settings.episodic_min_episodes = 1
        msg = "Please contact me at jo@acme.io about pricing"
        r = client.post("/chat", json={"message": msg, "key": site["public_key"]}).json()
        assert r["session_id"]
        items = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "jo@acme.io" and items[0]["source"] == "conversation"
        assert items[0]["conversation_id"]          # linked to its transcript
        assert "jo@acme.io" not in items[0]["summary"]  # contact turns are not questions
        # A turn holding someone's contact details is never replayed to anyone.
        again = client.post("/chat", json={"message": msg, "key": site["public_key"]}).json()
        assert again["intent"] != "cached"
        ins = client.get(f"/tenant/websites/{site['id']}/insights", headers=h).json()
        assert ins["funnel"][-1] == {"stage": "leads", "label": "Left their details",
                                     "count": 2}


def test_integration_urls_are_validated():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        url = f"/tenant/websites/{site['id']}/integrations"
        cfg = client.get(url, headers=h).json()
        assert cfg["webhook_secret"].startswith("whsec_") and cfg["webhook_url"] is None
        assert client.put(url, headers=h, json={
            "webhook_url": "http://127.0.0.1:9000/hook"}).status_code == 422
        assert client.put(url, headers=h, json={
            "slack_webhook_url": "https://evil.example/hook"}).status_code == 422
        saved = client.put(url, headers=h, json={
            "webhook_url": "https://hooks.example.com/fb",
            "slack_webhook_url": "https://hooks.slack.com/services/T/B/X",
            "hot_lead_score": 50, "rotate_secret": True}).json()
        assert saved["webhook_secret"] != cfg["webhook_secret"]


def test_delivery_signs_the_webhook_and_alerts_slack_when_hot(monkeypatch):
    monkeypatch.setattr(delivery, "RETRY_DELAYS", (0, 0))
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    with TestClient(app) as client:
        h, site = _tenant_site(client)
        # The lead first (its background delivery finds nothing configured, so
        # no real network), then the integrations the mock transport receives.
        client.post("/leads", json={"key": site["public_key"], "email": "cold@acme.io"})
        cfg = client.put(f"/tenant/websites/{site['id']}/integrations", headers=h, json={
            "webhook_url": "https://hooks.example.com/fb",
            "slack_webhook_url": "https://hooks.slack.com/services/T/B/X",
            "hot_lead_score": 50}).json()
        lead = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"][0]

    async def run(hot: bool):
        try:
            return await delivery.deliver_lead(
                {**lead, "score": 90 if hot else lead["score"]},
                transport=httpx.MockTransport(handler))
        finally:
            await dispose_engine()

    assert asyncio.run(run(hot=False)) is None
    assert [r.url.host for r in sent] == ["hooks.example.com"]     # cold: no Slack
    hook = sent[0]
    parts = dict(p.split("=", 1) for p in hook.headers["X-FluidBuddha-Signature"].split(","))
    expected = hmac.new(cfg["webhook_secret"].encode(),
                        f"{parts['t']}.".encode() + hook.content, hashlib.sha256).hexdigest()
    assert parts["v1"] == expected
    assert json.loads(hook.content)["lead"]["email"] == "cold@acme.io"

    sent.clear()
    assert asyncio.run(run(hot=True)) is None
    assert [r.url.host for r in sent] == ["hooks.example.com", "hooks.slack.com"]
    assert "cold@acme.io" in json.loads(sent[1].content)["text"]

    with TestClient(app) as client:
        delivered = client.get(f"/tenant/websites/{site['id']}/leads",
                               headers=h).json()["items"][0]
    assert delivered["delivered_at"] and delivered["delivery_error"] is None


@pytest.mark.parametrize("status_code,attempts", [(503, 3), (400, 1)])
def test_delivery_retries_server_errors_only(monkeypatch, status_code, attempts):
    monkeypatch.setattr(delivery, "RETRY_DELAYS", (0, 0))
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status_code)

    with pytest.raises(RuntimeError):
        asyncio.run(delivery._post("https://hooks.example.com/fb", b"{}", {},
                                   httpx.MockTransport(handler)))
    assert len(calls) == attempts
