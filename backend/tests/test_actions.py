"""
Actions marketplace + custom components (M2-8): typed inputs checked on the
server, nothing runs before the visitor confirms, the model can't set an
amount, Razorpay links against a fake, paid status back to the lead, trial and
meeting actions, and tenant components (template + sandboxed iframe).
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

from app.actions import run as runner
from app.actions.fields import (
    ActionConfigError, InputError, clean_config, fields_for, rupees, validate_inputs,
)
from app.leads import delivery
from app.main import app
from app.orchestrator import custom_components as cc

PRICES = [{"key": "growth", "label": "Growth plan", "amount": 1499900},
          {"key": "starter", "label": "Starter plan", "amount": 499900}]


def _tenant(client: TestClient, role_email: str | None = None) -> dict:
    tok = client.post("/auth/register", json={
        "email": role_email or f"act_{uuid.uuid4().hex[:10]}@example.com",
        "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _site(client: TestClient, h: dict, name: str = "Action Co") -> dict:
    return client.post("/tenant/websites", json={"name": name}, headers=h).json()


class FakeRazorpay:
    """Records calls; answers like Razorpay's Payment Links API."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.status = "created"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append((request.method, request.url.path, body))
        assert request.headers["authorization"].startswith("Basic ")
        if request.method == "POST" and request.url.path.endswith("/payment_links"):
            return httpx.Response(200, json={"id": "plink_" + uuid.uuid4().hex[:12],
                                             "short_url": "https://rzp.io/i/abc123",
                                             "amount": body["amount"], "status": "created"})
        if request.method == "GET" and "/payment_links/" in request.url.path:
            return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[1],
                                             "status": self.status, "amount_paid": 1499900})
        return httpx.Response(404, json={"error": {"description": "not found"}})


@pytest.fixture
def fake_rzp(monkeypatch):
    fake = FakeRazorpay()
    monkeypatch.setattr(runner, "_razorpay_transport", httpx.MockTransport(fake))
    monkeypatch.setattr(delivery, "RETRY_DELAYS", (0, 0))
    return fake


# ---- inputs and settings ----------------------------------------------------------

def test_inputs_are_typed_and_checked():
    fields = fields_for("payment_link", {"prices": PRICES})
    ok = validate_inputs(fields, {"plan": "growth", "email": "Ana@Buyer.example", "amount": 1,
                                  "name": "  Ana   Rao "})
    assert ok == {"plan": "growth", "email": "ana@buyer.example", "name": "Ana Rao"}  # amount dropped
    for bad in ({"plan": "platinum", "email": "a@b.co"}, {"plan": "growth"},
                {"plan": "growth", "email": "not-an-email"}):
        with pytest.raises(InputError):
            validate_inputs(fields, bad)
    quote = fields_for("quote_request", {})
    with pytest.raises(InputError):
        validate_inputs(quote, {"email": "a@b.co", "details": "x", "quantity": "lots"})
    assert validate_inputs(quote, {"email": "a@b.co", "details": "x", "quantity": "12"})["quantity"] == 12
    assert rupees(1499900) == "₹14,999" and rupees(14999950) == "₹1,49,999.50"


def test_settings_are_checked():
    for kind, cfg in (("payment_link", {"key_id": "nope", "prices": PRICES}),
                      ("payment_link", {"key_id": "rzp_test_abc123", "prices": [{"key": "x", "amount": 5}]}),
                      ("trial", {"url": "http://insecure.example/hook"}),
                      ("meeting_link", {"booking_url": "javascript:alert(1)"}),
                      ("webhook", {"url": "https://ok.example/h", "fields": []}),
                      ("teleport", {})):
        with pytest.raises(ActionConfigError):
            clean_config(kind, cfg)
    cfg = clean_config("webhook", {"url": "https://ok.example/h", "fields": [
        {"key": "size", "label": "Team size", "type": "integer", "required": True}]})
    assert cfg["fields"][0]["type"] == "integer" and cfg["max_per_hour"] == 20


def test_meeting_link_prefills_the_booking_page():
    url = runner.meeting_url({"booking_url": "https://calendly.com/acme/demo?month=2026-11",
                              "style": "calendly"},
                             {"name": "Ana Rao", "email": "ana@buyer.example", "topic": "Pricing"})
    assert url.startswith("https://calendly.com/acme/demo?")
    assert "name=Ana+Rao" in url and "email=ana%40buyer.example" in url and "a1=Pricing" in url
    assert "month=2026-11" in url


# ---- console --------------------------------------------------------------------

def test_console_manages_actions_and_keeps_secrets(fake_rzp):
    with TestClient(app) as client:
        h = _tenant(client)
        site = _site(client, h)
        base = f"/tenant/websites/{site['id']}/actions"
        good = {"kind": "payment_link", "name": "buy_plan", "label": "Pay for a plan",
                "description": "Take payment for a plan.",
                "config": {"key_id": "rzp_test_abc123", "prices": PRICES},
                "secrets": {"key_secret": "sk_very_secret", "webhook_secret": "wh_secret"}}
        assert client.post(base, json={**good, "secrets": {}}, headers=h).status_code == 422
        assert client.post(base, json={**good, "name": "Bad Name"}, headers=h).status_code == 422
        made = client.post(base, json=good, headers=h)
        assert made.status_code == 201, made.text
        a = made.json()
        assert a["has_secret"] and "sk_very_secret" not in made.text
        assert a["razorpay_webhook_url"].endswith(f"/actions/razorpay/{a['id']}/webhook")
        assert client.post(base, json=good, headers=h).status_code == 422          # name taken
        # Blank secrets keep the stored ones.
        upd = client.put(f"{base}/{a['id']}", json={**good, "label": "Buy a plan", "secrets": {}},
                         headers=h)
        assert upd.status_code == 200 and upd.json()["label"] == "Buy a plan"
        listed = client.get(base, headers=h)
        assert "sk_very_secret" not in listed.text and len(listed.json()["actions"]) == 1
        # Another tenant can't see it.
        assert client.get(base, headers=_tenant(client)).status_code == 404


# ---- the payment flow -------------------------------------------------------------

def _payment_site(client: TestClient) -> tuple[dict, dict, str]:
    h = _tenant(client)
    site = _site(client, h)
    a = client.post(f"/tenant/websites/{site['id']}/actions", headers=h, json={
        "kind": "payment_link", "name": "buy_plan", "label": "Pay for a plan",
        "config": {"key_id": "rzp_test_abc123", "prices": PRICES},
        "secrets": {"key_secret": "sk_very_secret", "webhook_secret": "wh_secret"}}).json()
    return h, site, a["id"]


def _ask_to_pay(client: TestClient, key: str) -> dict:
    r = client.post("/chat", json={
        "message": f"I want to pay for the growth plan, my email is ana.{uuid.uuid4().hex[:4]}@buyer.example",
        "key": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_payment_needs_confirmation_and_comes_back_paid(fake_rzp):
    with TestClient(app) as client:
        h, site, action_id = _payment_site(client)
        key = site["public_key"]
        r = _ask_to_pay(client, key)
        [card] = r["proposals"]
        assert card["label"] == "Pay for a plan"
        assert {"label": "Amount", "value": "₹14,999"} in card["summary"]
        assert fake_rzp.calls == []                       # nothing happens before confirming
        sid = r["session_id"]
        runs = client.get(f"/tenant/websites/{site['id']}/action-runs", headers=h).json()["runs"]
        assert runs[0]["status"] == "proposed" and runs[0]["amount"] == 1499900

        # Only this conversation can confirm it.
        assert client.post("/actions/confirm", json={"key": key, "session_id": "someone-else",
                                                     "run_id": card["id"]}).status_code == 404
        done = client.post("/actions/confirm", json={"key": key, "session_id": sid,
                                                     "run_id": card["id"]})
        assert done.status_code == 200, done.text
        out = done.json()
        assert out["status"] == "done" and out["url"] == "https://rzp.io/i/abc123"
        [(method, path, body)] = fake_rzp.calls
        assert path.endswith("/payment_links") and body["amount"] == 1499900   # from the price list
        assert body["customer"]["email"].endswith("@buyer.example")
        # A second click doesn't charge twice.
        again = client.post("/actions/confirm", json={"key": key, "session_id": sid,
                                                      "run_id": card["id"]}).json()
        assert again["status"] == "done" and len(fake_rzp.calls) == 1

        lead = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"][0]
        assert lead["source"] == "payment" and lead["paid_at"] is None

        # Razorpay says it's paid (signed webhook); a bad signature is refused.
        run = client.get(f"/tenant/websites/{site['id']}/action-runs", headers=h).json()["runs"][0]
        ext = _external_id(run["id"])
        event = json.dumps({"event": "payment_link.paid", "payload": {"payment_link": {"entity": {
            "id": ext, "amount_paid": 1499900, "status": "paid"}}}}).encode()
        hook = f"/actions/razorpay/{action_id}/webhook"
        assert client.post(hook, content=event, headers={"X-Razorpay-Signature": "bad"}).status_code == 400
        sig = hmac.new(b"wh_secret", event, hashlib.sha256).hexdigest()
        assert client.post(hook, content=event, headers={"X-Razorpay-Signature": sig}).status_code == 200
        lead = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"][0]
        assert lead["paid_at"] and lead["paid_amount"] == 1499900 and lead["score"] >= 90
        assert client.get(f"/tenant/websites/{site['id']}/action-runs",
                          headers=h).json()["runs"][0]["status"] == "paid"


def _external_id(run_id: str) -> str:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import get_settings

    async def go():
        eng = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with eng.connect() as c:
                return (await c.execute(text("SELECT external_id FROM action_runs WHERE id = :id"),
                                        {"id": uuid.UUID(run_id)})).scalar()
        finally:
            await eng.dispose()
    return asyncio.run(go())


def _with_db(job):
    """Run a job with a throwaway engine on this thread's own event loop."""
    from contextlib import asynccontextmanager
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import get_settings

    async def go():
        eng = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)

        @asynccontextmanager
        async def factory():
            async with AsyncSession(eng, expire_on_commit=False) as db:
                yield db
        try:
            return await job(factory)
        finally:
            await eng.dispose()
    return asyncio.run(go())


def test_poll_marks_paid_and_price_changes_are_caught(fake_rzp):
    from app.routes.actions import check_payments
    with TestClient(app) as client:
        h, site, action_id = _payment_site(client)
        key = site["public_key"]
        r = _ask_to_pay(client, key)
        client.post("/actions/confirm", json={"key": key, "session_id": r["session_id"],
                                              "run_id": r["proposals"][0]["id"]})
        fake_rzp.status = "paid"
        assert _with_db(check_payments) >= 1
        lead = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"][0]
        assert lead["paid_at"]

        # The model can't change the amount: a price edited after the proposal
        # makes the confirmation fail instead of charging the old or new price.
        r = _ask_to_pay(client, key)
        client.put(f"/tenant/websites/{site['id']}/actions/{action_id}", headers=h, json={
            "kind": "payment_link", "name": "buy_plan", "label": "Pay for a plan",
            "config": {"key_id": "rzp_test_abc123",
                       "prices": [{**PRICES[0], "amount": 1999900}, PRICES[1]]}})
        calls = len(fake_rzp.calls)
        out = client.post("/actions/confirm", json={"key": key, "session_id": r["session_id"],
                                                    "run_id": r["proposals"][0]["id"]}).json()
        assert out["status"] == "failed" and "price list" in out["error"]
        assert len([c for c in fake_rzp.calls[calls:] if c[0] == "POST"]) == 0

        # Cancel: nothing runs, and it can't be confirmed afterwards.
        r = _ask_to_pay(client, key)
        body = {"key": key, "session_id": r["session_id"], "run_id": r["proposals"][0]["id"]}
        assert client.post("/actions/cancel", json=body).json()["status"] == "cancelled"
        assert client.post("/actions/confirm", json=body).json()["status"] == "cancelled"


# ---- trial, quote, erasure --------------------------------------------------------

def test_trial_quote_and_erasure(monkeypatch, fake_rzp):
    seen: list[httpx.Request] = []

    def backend(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "trial.example.com":
            return httpx.Response(200, json={"login_url": "https://app.example.com/login?t=xyz"})
        return httpx.Response(200, json={})
    monkeypatch.setattr(runner, "_transport", httpx.MockTransport(backend))

    with TestClient(app) as client:
        h = _tenant(client)
        site = _site(client, h, "Trial Co")
        base = f"/tenant/websites/{site['id']}/actions"
        trial = client.post(base, headers=h, json={
            "kind": "trial", "name": "start_trial", "label": "Start a free trial",
            "config": {"url": "https://trial.example.com/hook"}}).json()
        client.post(base, headers=h, json={"kind": "quote_request", "name": "get_quote",
                                           "label": "Request a quote", "config": {}})
        secret = client.get(f"{base}/{trial['id']}/secret", headers=h).json()["signing_secret"]
        assert secret.startswith("whsec_")

        key = site["public_key"]
        r = client.post("/chat", json={"message": "please start a trial for me, bo@corp.example",
                                       "key": key}).json()
        [card] = r["proposals"]
        out = client.post("/actions/confirm", json={"key": key, "session_id": r["session_id"],
                                                     "run_id": card["id"]}).json()
        assert out["status"] == "done" and out["url"] == "https://app.example.com/login?t=xyz"
        req = seen[0]
        body = req.content
        ts, mac = dict(p.split("=", 1) for p in req.headers["x-fluidbuddha-signature"].split(",")).values()
        assert hmac.compare_digest(mac, hmac.new(secret.encode(), f"{ts}.".encode() + body,
                                                 hashlib.sha256).hexdigest())
        assert json.loads(body)["visitor"]["email"] == "bo@corp.example"
        assert req.headers["idempotency-key"] == card["id"]

        r = client.post("/chat", json={"message": "I need a quote for 40 seats, cy@corp.example",
                                       "key": key}).json()
        out = client.post("/actions/confirm", json={"key": key, "session_id": r["session_id"],
                                                    "run_id": r["proposals"][0]["id"]}).json()
        assert out["status"] == "done"
        sources = {x["source"] for x in client.get(f"/tenant/websites/{site['id']}/leads",
                                                     headers=h).json()["items"]}
        assert {"trial", "quote"} <= sources

        # Erasing the visitor removes their action runs too.
        erased = client.post(f"/tenant/websites/{site['id']}/privacy/erase", headers=h,
                             json={"email": "bo@corp.example"}).json()
        assert erased["action_runs"] >= 1
        runs = client.get(f"/tenant/websites/{site['id']}/action-runs", headers=h).json()["runs"]
        assert all(r_["inputs"].get("email") != "bo@corp.example" for r_ in runs)


def test_only_admins_change_actions():
    from app.auth.roles import required_role
    assert required_role("POST", "/tenant/websites/{website_id}/actions") == "admin"
    assert required_role("PUT", "/tenant/websites/{website_id}/actions/{action_id}") == "admin"
    assert required_role("GET", "/tenant/websites/{website_id}/actions") == "viewer"
    assert required_role("GET", "/tenant/websites/{website_id}/action-runs") == "viewer"
    assert required_role("GET", "/tenant/websites/{website_id}/actions/{action_id}/secret") == "admin"
    assert required_role("POST", "/tenant/websites/{website_id}/components") == "editor"


# ---- custom components --------------------------------------------------------------

PLAN_BUILDER = {
    "name": "plan_builder", "label": "Plan builder", "kind": "template",
    "description": "Lets the visitor size a plan by seats.",
    "props_schema": {"type": "object", "properties": {
        "seats": {"type": "integer", "minimum": 1, "maximum": 500, "default": 10},
        "plan": {"type": "string", "enum": ["growth", "scale"], "default": "growth"}},
        "required": []},
    "template": {"base": "configurator", "state": {
        "controls": [{"key": "seats", "label": "Seats", "type": "slider", "min": 1, "max": 500,
                      "value": "{{seats}}"}],
        "outputs": [{"label": "Monthly ({{plan}})", "expr": "seats * 999", "format": "currency"}]}},
}


def test_component_specs_are_checked():
    for bad in ({**PLAN_BUILDER, "name": "chart"},
                {**PLAN_BUILDER, "template": {"base": "script", "state": {}}},
                {**PLAN_BUILDER, "template": {"base": "table", "state": {"x": "{{nope}}"}}},
                {**PLAN_BUILDER, "kind": "iframe", "iframe_url": "http://plain.example"},
                {**PLAN_BUILDER, "props_schema": {"type": "object", "properties": {
                    "seats": {"type": "function"}}}}):
        with pytest.raises(cc.ComponentSpecError):
            cc.clean_spec(bad)
    spec = cc.clean_spec(PLAN_BUILDER)
    comp = cc.CustomComponent(id=uuid.uuid4(), site_key="x", **spec)
    ctype, state = cc.render(comp, {"seats": 25})
    assert ctype == "configurator" and state["controls"][0]["value"] == 25
    assert state["outputs"][0]["label"] == "Monthly (growth)"
    for bad_props in ({"seats": "lots"}, {"seats": 9000}, {"plan": "free"}):
        with pytest.raises(cc.PropsError):
            cc.render(comp, bad_props)
    frame = cc.CustomComponent(id=uuid.uuid4(), site_key="x", **cc.clean_spec({
        **PLAN_BUILDER, "kind": "iframe", "template": None, "iframe_url": "https://tools.acme.example/calc"}))
    ctype, state = cc.render(frame, {"seats": 3, "src": "https://evil.example"})
    assert ctype == "embed" and state == {"src": "https://tools.acme.example/calc",
                                          "name": "plan_builder", "props": {"seats": 3, "plan": "growth"}}


def test_agent_renders_a_tenant_component():
    with TestClient(app) as client:
        h = _tenant(client)
        site = _site(client, h, "Builder Co")
        base = f"/tenant/websites/{site['id']}/components"
        made = client.post(base, json=PLAN_BUILDER, headers=h)
        assert made.status_code == 201, made.text
        assert client.post(base, json=PLAN_BUILDER, headers=h).status_code == 422   # name taken
        prev = client.post(f"{base}/preview", headers=h,
                           json={"spec": PLAN_BUILDER, "props": {"seats": 7}}).json()
        assert prev["component_type"] == "configurator"
        assert prev["initial_state"]["controls"][0]["value"] == 7

        r = client.post("/chat", json={"message": "show me plan builder for 25",
                                       "key": site["public_key"]}).json()
        [comp] = r["components"]
        assert comp["component_type"] == "configurator"
        assert comp["initial_state"]["controls"][0]["value"] == 25
