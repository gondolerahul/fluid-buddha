"""
Insights v2 + weekly digest (M2-5): the turn classifier (rules and the model's
answer), what the console gets from it, sending a feature request on, and the
weekly digest's content, timing, recipients and unsubscribe.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.base import LLMResponse
from app.config import get_settings
from app.insights.classify import classify, classify_pending, parse_model_output, rules
from app.insights.store import group_requests, record_turn
from app.notify import digest


def _run(fn):
    """Run ``fn(db)`` on a throwaway engine with its own loop."""
    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await fn(db)
        finally:
            await engine.dispose()
    return asyncio.run(go())


# ---- the classifier -------------------------------------------------------------

def test_rules():
    s = rules("Intercom is cheaper — this looks too expensive for us", competitors=["Intercom", "Drift"])
    assert s.objections == ["price"] and s.competitors == ["Intercom"] and not s.buying_signal
    assert rules("How much does it cost?").objections == []        # a question, not an objection
    assert rules("Is our data encrypted? We need SOC 2").objections == ["security"]
    assert rules("We can't do this until next quarter").objections == ["timing"]
    assert rules("How long does it take to set up?").objections == ["effort"]
    assert rules("Do you integrate with HubSpot?").objections == ["integration"]
    # "Do you support X?" is a feature request only when the agent had no answer.
    assert rules("Do you support Salesforce?", found=True).feature_request is None
    assert rules("Do you support Salesforce?", found=False).feature_request == "Do you support Salesforce?"
    assert rules("It would be great if it had a Slack app").feature_request
    assert rules("Can we book a demo for 40 seats?").buying_signal
    assert rules("I'm comparing you with drift.").competitors == []   # not on the list
    assert rules("vs DRIFT?", competitors=["Drift"]).competitors == ["Drift"]
    assert rules("Driftwood pricing", competitors=["Drift"]).competitors == []   # whole words only


def test_model_output_is_checked():
    good = parse_model_output(
        'Sure! {"objections": ["Price", "budgeting"], "competitors": ["intercom", "Zendesk"], '
        '"feature_request": "a Slack app", "buying_signal": true} hope that helps',
        question="Intercom has a Slack app", competitors=["Intercom"])
    assert good.objections == ["price"]                       # unknown types dropped
    assert good.competitors == ["Intercom", "Zendesk"]        # the list's spelling kept
    assert good.feature_request == "a Slack app" and good.buying_signal is True
    assert parse_model_output("no json here", question="x") is None
    assert parse_model_output('{"objections": "price"}', question="x") is None
    nulls = parse_model_output('{"objections": [], "competitors": [], "feature_request": "null", '
                               '"buying_signal": "yes"}', question="x")
    assert nulls.feature_request is None and nulls.buying_signal is False


def test_classify_falls_back_to_rules_when_the_model_fails():
    class Garbage:
        async def generate(self, **_):
            return LLMResponse(text="I think it's about price.")

    class Broken:
        async def generate(self, **_):
            raise RuntimeError("quota")

    class Good:
        async def generate(self, **kw):
            assert "Known competitors: Drift" in kw["system"]
            return LLMResponse(text='{"objections": ["trust"], "competitors": [], '
                                    '"feature_request": null, "buying_signal": false}')

    q = "Too expensive compared to Drift"
    for llm in (Garbage(), Broken()):
        s = asyncio.run(classify(q, competitors=["Drift"], llm=llm))
        assert s.objections == ["price"] and s.competitors == ["Drift"]
    s = asyncio.run(classify(q, competitors=["Drift"], llm=Good()))
    assert s.objections == ["trust"] and s.competitors == ["Drift"]   # list match always added


def test_feature_requests_are_grouped():
    items = [{"text": t, "at": f"2026-11-0{i}"} for i, t in enumerate([
        "Do you support Salesforce sync?", "Please add a Salesforce sync", "A Slack app would be great",
        "Salesforce sync support?", "Export to CSV"], start=1)]
    groups = group_requests(items)
    assert groups[0]["count"] == 3 and "Salesforce" in groups[0]["text"]
    assert {g["text"] for g in groups[1:]} == {"A Slack app would be great", "Export to CSV"}
    assert len(groups[0]["examples"]) == 3


# ---- insights through the console -----------------------------------------------

def _tenant(client: TestClient) -> tuple[dict, str]:
    email = f"ins2_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register", json={"email": email, "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, email


def _record(site_key: str, session: str, question: str, found: bool = True) -> None:
    async def go(db):
        await record_turn(db, site_key=site_key, session_id=session, channel="text", question=question,
                          answer="ok", intent="capability",
                          grounding={"found": found, "confidence": 0.5, "sources": []})
        await db.commit()
    _run(go)


def _classify_all() -> None:
    async def go(db):
        while await classify_pending(db, batch=200):
            pass
    _run(go)


def test_signals_show_in_insights_and_requests_can_be_sent_on():
    from app.main import app
    from app.routes import insights as insights_routes

    with TestClient(app) as client:
        h, _ = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Signal Co"}, headers=h).json()
        base = f"/tenant/websites/{site['id']}"
        client.put(f"{base}/profile", json={"competitors": ["Intercom", " intercom ", "Drift"]}, headers=h)
        assert client.get(f"{base}/profile", headers=h).json()["competitors"] == ["Intercom", "Drift"]

    sk = site["site_key"]
    _record(sk, "s1", "Intercom is cheaper, this is too expensive for us")
    _record(sk, "s1", "Can we book a demo for 30 seats?")
    _record(sk, "s2", "Do you support Salesforce sync?", found=False)
    _record(sk, "s2", "Please add a Salesforce sync")
    _record(sk, "s3", "How does it compare to Drift? Our budget is tight")
    _classify_all()

    with TestClient(app) as client:
        sig = client.get(f"{base}/insights/signals", headers=h).json()
        assert sig["pending"] == 0 and sig["classified"] == 5
        price = next(o for o in sig["objections"] if o["type"] == "price")
        assert price["count"] == 2 and price["label"] == "Price" and len(price["examples"]) == 2
        assert {c["name"]: c["count"] for c in sig["competitors"]} == {"Intercom": 1, "Drift": 1}
        assert sig["requests"][0]["count"] == 2
        assert sig["buying_signals"] == {"turns": 1, "conversations": 1}
        conv = price["examples"][0]["conversation_id"]
        assert client.get(f"{base}/conversations/{conv}", headers=h).status_code == 200

        req = {"text": sig["requests"][0]["text"], "count": 2, "examples": ["Please add a Salesforce sync"]}
        assert client.post(f"{base}/insights/requests/send", json={**req, "channel": "slack"},
                           headers=h).status_code == 409   # no Slack set up yet
        sent = client.post(f"{base}/insights/requests/send",
                           json={**req, "channel": "email", "email": "product@example.com"}, headers=h)
        assert sent.status_code == 200
        got: list[httpx.Request] = []
        insights_routes._transport = httpx.MockTransport(lambda r: got.append(r) or httpx.Response(200))
        try:
            client.put(f"{base}/integrations", json={"webhook_url": "https://hooks.example.com/fb",
                                                     "slack_webhook_url": None, "hot_lead_score": 70}, headers=h)
            assert client.post(f"{base}/insights/requests/send", json={**req, "channel": "webhook"},
                               headers=h).json()["sent"]
        finally:
            insights_routes._transport = None
        body = json.loads(got[0].content)
        assert body["event"] == "feature_request" and body["count"] == 2
        assert got[0].headers["X-FluidBuddha-Signature"].startswith("t=")

        h2, _ = _tenant(client)
        assert client.get(f"{base}/insights/signals", headers=h2).status_code == 404

    async def outbox(db):
        return (await db.execute(text("SELECT subject FROM email_outbox WHERE to_addr = 'product@example.com' "
                                      "AND kind = 'feature_request' ORDER BY id DESC LIMIT 1"))).scalar()
    assert _run(outbox).startswith("Feature request:")


# ---- the weekly digest ------------------------------------------------------------

def test_digest_is_due_monday_9am_local():
    ist = ZoneInfo("Asia/Kolkata")
    mon_0900 = datetime(2026, 11, 9, 9, 0, tzinfo=ist).astimezone(timezone.utc)
    assert digest.due(mon_0900, "Asia/Kolkata") == "2026-W46"
    assert digest.due(mon_0900 - timedelta(minutes=1), "Asia/Kolkata") is None
    assert digest.due(mon_0900 + timedelta(hours=14), "Asia/Kolkata") == "2026-W46"   # later Monday
    assert digest.due(mon_0900 + timedelta(days=1), "Asia/Kolkata") is None           # Tuesday: missed
    # The same instant is Sunday evening in New York: not yet.
    assert digest.due(mon_0900, "America/New_York") is None
    assert digest.due(datetime(2026, 11, 9, 14, 0, tzinfo=timezone.utc), "America/New_York") == "2026-W46"
    assert digest.due(mon_0900, "Not/AZone") == "2026-W46"   # falls back to India time
    assert digest.valid_timezone("Europe/London") and not digest.valid_timezone("Mars/Base")


def _next_monday_10am_ist() -> datetime:
    local = datetime.now(ZoneInfo("Asia/Kolkata"))
    monday = (local + timedelta(days=(7 - local.weekday()) % 7 or 7)).replace(
        hour=10, minute=0, second=0, microsecond=0)
    return monday.astimezone(timezone.utc)


def test_weekly_digest_content_recipients_and_unsubscribe():
    from app.main import app

    with TestClient(app) as client:
        h, owner = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Digest Co"}, headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/profile", json={"competitors": ["Drift"]}, headers=h)
        cfg = client.get("/tenant/digest", headers=h).json()
        # Until someone chooses, the Owners get it, Mondays 9:00 India time.
        assert cfg["recipients"] == [{"email": owner, "unsubscribed": False}]
        assert cfg["enabled"] and not cfg["chosen"] and cfg["timezone"] == "Asia/Kolkata"
        assert datetime.fromisoformat(cfg["next_send"]).weekday() == 0
        tenant_id = uuid.UUID(client.get("/auth/me", headers=h).json()["id"])
        assert client.put("/tenant/digest", json={"enabled": True, "recipients": [owner],
                                                  "timezone": "Mars/Base"}, headers=h).status_code == 422

    sk = site["site_key"]
    _record(sk, "d1", "Too expensive compared to Drift")
    _record(sk, "d1", "Do you have a Shopify app?", found=False)
    _record(sk, "d2", "Too expensive compared to Drift")
    _classify_all()

    with TestClient(app) as client:
        pv = client.get("/tenant/digest/preview", headers=h).json()
        data = pv["data"]
        assert data["conversations"] == 2 and data["leads"] == 0
        assert data["top_questions"][0] == {"question": "Too expensive compared to Drift", "count": 2}
        assert data["new_gaps"][0]["question"] == "Do you have a Shopify app?"
        assert data["objections"][0]["type"] == "price" and data["competitors"] == [{"name": "Drift", "count": 2}]
        assert "2 conversations" in pv["subject"] and "Drift: 2" in pv["text"]
        assert "<script" not in pv["html"]
        assert client.post("/tenant/digest/send-test", headers=h).json() == {"queued": 1, "to": owner}

        cfg = client.put("/tenant/digest", json={"enabled": True, "recipients": [owner, "cmo@example.com"],
                                                  "timezone": "Asia/Kolkata"}, headers=h).json()
        assert cfg["chosen"] and [r["email"] for r in cfg["recipients"]] == [owner, "cmo@example.com"]

    monday = _next_monday_10am_ist()
    send = lambda when: _run(lambda db: digest.send_due(db, now=when, tenant_ids=[tenant_id]))  # noqa: E731
    assert send(monday - timedelta(days=1)) == 0          # Sunday: not due
    assert send(monday) == 2                              # both recipients
    assert send(monday + timedelta(hours=3)) == 0         # once a week

    async def mail(db):
        rows = (await db.execute(text(
            "SELECT to_addr, headers, html_body FROM email_outbox WHERE kind = 'digest' AND tenant_id = :t "
            "AND idem_key IS NOT NULL"), {"t": tenant_id})).mappings().all()
        token = (await db.execute(text(
            "SELECT token FROM digest_tokens WHERE tenant_id = :t AND email = 'cmo@example.com'"),
            {"t": tenant_id})).scalar()
        return rows, token
    rows, token = _run(mail)
    assert sorted(r["to_addr"] for r in rows) == sorted([owner, "cmo@example.com"])
    headers = json.loads(rows[0]["headers"]) if isinstance(rows[0]["headers"], str) else rows[0]["headers"]
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/digest/unsubscribe?t=" in headers["List-Unsubscribe"] and "@" not in headers["List-Unsubscribe"]

    with TestClient(app) as client:
        page = client.get(f"/digest/unsubscribe?t={token}")
        assert page.status_code == 200 and "Unsubscribe</button>" in page.text   # GET changes nothing
        assert not client.get("/tenant/digest", headers=h).json()["recipients"][1]["unsubscribed"]
        done = client.post(f"/digest/unsubscribe?t={token}")
        assert "cmo@example.com won't get the weekly digest" in done.text
        assert "isn't valid" in client.post("/digest/unsubscribe?t=not-a-real-token").text
        cfg = client.get("/tenant/digest", headers=h).json()
        assert cfg["recipients"][1] == {"email": "cmo@example.com", "unsubscribed": True}
        # An admin listing them again doesn't override their choice.
        cfg = client.put("/tenant/digest", json={"enabled": True, "recipients": [owner, "cmo@example.com"],
                                                  "timezone": "Asia/Kolkata"}, headers=h).json()
        assert cfg["recipients"][1]["unsubscribed"] is True

    async def forget_week(db):   # as if this week hadn't been sent yet
        await db.execute(text("DELETE FROM digest_runs WHERE tenant_id = :t"), {"t": tenant_id})
        await db.execute(text("DELETE FROM email_outbox WHERE kind = 'digest' AND tenant_id = :t"),
                         {"t": tenant_id})
        await db.commit()
    _run(forget_week)
    assert send(monday) == 1                              # the unsubscribed address is skipped

    with TestClient(app) as client:
        off = client.put("/tenant/digest", json={"enabled": False, "recipients": [owner],
                                                  "timezone": "Asia/Kolkata"}, headers=h).json()
        assert off["enabled"] is False
    _run(forget_week)
    assert send(monday) == 0                              # switched off


def test_a_quiet_week_sends_nothing():
    from app.main import app

    with TestClient(app) as client:
        h, _ = _tenant(client)
        client.post("/tenant/websites", json={"name": "Quiet Co"}, headers=h)
        tenant_id = uuid.UUID(client.get("/auth/me", headers=h).json()["id"])
    assert _run(lambda db: digest.send_due(db, now=_next_monday_10am_ist(), tenant_ids=[tenant_id])) == 0


@pytest.mark.parametrize("path", ["/tenant/digest", "/tenant/digest/preview"])
def test_digest_settings_are_for_admins(path):
    from app.auth.roles import required_role
    assert required_role("GET", path) == "admin" and required_role("PUT", "/tenant/digest") == "admin"
