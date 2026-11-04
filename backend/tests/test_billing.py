"""
Billing with Razorpay (WS12): the catalog, signatures, checkout and plan
changes, webhooks (idempotent), overage add-ons at the cycle change, the Free
cap on public turns, and cost per conversation.

Razorpay is faked in memory (the API calls billing makes, with Razorpay's
shapes); nothing leaves the machine.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import itertools
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.billing import plans as catalog
from app.billing.razorpay import Razorpay, webhook_signature_ok
from app.config import get_settings

KEY_ID, KEY_SECRET, HOOK_SECRET = "rzp_test_fake", "fake-secret", "hook-secret"


class FakeRazorpay:
    """Just enough of api.razorpay.com/v1 for billing."""

    def __init__(self) -> None:
        self.plans: dict[str, dict] = {}
        self.subs: dict[str, dict] = {}
        self.addons: list[dict] = []
        self.links: list[dict] = []
        self.links_down = False
        self.calls: list[tuple[str, str]] = []
        self._ids = itertools.count(1)

    def _id(self, prefix: str) -> str:
        # Unique across runs, like Razorpay's (the test database persists).
        return f"{prefix}_{next(self._ids):04d}{uuid.uuid4().hex[:10]}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        path = request.url.path.removeprefix("/v1")
        body = json.loads(request.content or b"{}")
        self.calls.append((request.method, path))
        if request.method == "POST" and path == "/plans":
            plan = {"id": self._id("plan"), **body}
            self.plans[plan["id"]] = plan
            return httpx.Response(200, json=plan)
        if request.method == "POST" and path == "/subscriptions":
            if body["plan_id"] not in self.plans:
                return httpx.Response(400, json={"error": {"description": "plan not found"}})
            sub = {"id": self._id("sub"), "status": "created", "plan_id": body["plan_id"],
                   "notes": body["notes"], "short_url": "https://rzp.io/i/fake",
                   "start_at": body.get("start_at")}
            self.subs[sub["id"]] = sub
            return httpx.Response(200, json=sub)
        if request.method == "POST" and path == "/payment_links":
            if self.links_down:
                return httpx.Response(500, json={"error": {"description": "server error"}})
            link = {"id": self._id("plink"), "status": "created",
                    "short_url": "https://rzp.io/rzp/fake", **body}
            self.links.append(link)
            return httpx.Response(200, json=link)
        if request.method == "GET" and path.startswith("/payment_links/"):
            link = next((l for l in self.links if l["id"] == path.rsplit("/", 1)[-1]), None)
            return httpx.Response(200, json=link) if link else httpx.Response(
                404, json={"error": {"description": "not found"}})
        parts = path.strip("/").split("/")
        if parts[0] == "plans" and len(parts) == 2 and request.method == "GET":
            plan = self.plans.get(parts[1])
            return (httpx.Response(200, json=plan) if plan else httpx.Response(
                400, json={"error": {"description": "The id provided does not exist"}}))
        if parts[0] == "subscriptions" and len(parts) >= 2:
            sub = self.subs.get(parts[1])
            if sub is None:
                return httpx.Response(404, json={"error": {"description": "no such subscription"}})
            if request.method == "GET":
                return httpx.Response(200, json=sub)
            if request.method == "PATCH" and sub.get("payment_method") == "upi":
                return httpx.Response(400, json={"error": {"description":
                    "subscriptions cannot be updated when payment mode is upi"}})
            if request.method == "PATCH":
                if body["schedule_change_at"] == "now":
                    sub["plan_id"] = body["plan_id"]
                else:
                    sub["scheduled_plan_id"] = body["plan_id"]
                return httpx.Response(200, json=sub)
            if parts[-1] == "cancel":
                if body["cancel_at_cycle_end"]:
                    sub["cancel_scheduled"] = True
                else:
                    sub["status"] = "cancelled"
                return httpx.Response(200, json=sub)
            if parts[-1] == "addons" and sub.get("payment_method") == "upi":
                return httpx.Response(400, json={"error": {"description":
                    "Addons can't be added for subscriptions when payment mode is upi"}})
            if parts[-1] == "addons":
                addon = {"id": self._id("ao"), "subscription_id": sub["id"], **body}
                self.addons.append(addon)
                return httpx.Response(200, json=addon)
        return httpx.Response(404, json={"error": {"description": "not faked"}})

    def activate(self, sub_id: str, start: datetime) -> dict:
        """What Razorpay reports once the first payment goes through."""
        sub = self.subs[sub_id]
        sub.update(status="active", current_start=int(start.timestamp()),
                   current_end=int((start + timedelta(days=30)).timestamp()))
        return sub


@pytest.fixture
def fake(monkeypatch):
    import app.routes.billing as routes

    fake = FakeRazorpay()
    transport = httpx.MockTransport(fake.handler)
    settings = get_settings()   # restored by conftest
    settings.razorpay_key_id, settings.razorpay_key_secret = KEY_ID, KEY_SECRET
    settings.razorpay_webhook_secret = HOOK_SECRET
    monkeypatch.setattr(routes, "client_from_settings",
                        lambda s, **kw: Razorpay(s.razorpay_key_id, s.razorpay_key_secret,
                                                 transport=transport))
    return fake


def _sql(sql: str, **params):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                res = await conn.execute(text(sql), params)
                return res.mappings().all() if res.returns_rows else None
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _usage(site_key: str, sessions: list[str], at: datetime | None = None, cost: float = 0.0):
    """Record one answered turn per session, optionally back-dated."""
    from app.analytics.usage import TurnMetrics, record_turn

    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                for s in sessions:
                    await record_turn(db, TurnMetrics(site_key=site_key, session_id=s,
                                                      channel="text", fast_in_tok=1000))
        finally:
            await engine.dispose()
    asyncio.run(run())
    if at is not None:
        _sql("UPDATE usage_events SET created_at = :at WHERE site_key = :k "
             "AND session_id = ANY(:s)", at=at, k=site_key, s=sessions)


def _tenant(client: TestClient) -> tuple[dict, dict]:
    email = f"bill_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register",
                      json={"email": email, "password": "supersecret1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    site = client.post("/tenant/websites", json={"name": "Billed Co"}, headers=h).json()
    return h, site


def _sign(body: bytes) -> str:
    return hmac.new(HOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _webhook(client, event: str, sub: dict, event_id: str | None = None, secret_ok=True):
    body = json.dumps({"entity": "event", "event": event,
                       "payload": {"subscription": {"entity": sub}}}).encode()
    return client.post("/billing/razorpay/webhook", content=body, headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": _sign(body) if secret_ok else "bad",
        "X-Razorpay-Event-Id": event_id or f"evt_{uuid.uuid4().hex}",
    })


# ---- pure ----------------------------------------------------------------------------

def test_catalog_defaults_and_overrides():
    s = get_settings()
    cat = catalog.catalog(s)
    assert cat["growth"].price == 39_900 and cat["scale"].price == 149_900
    assert cat["free"].overage is None and not cat["enterprise"].self_serve
    assert catalog.overage_amount(cat["growth"], 2_150) == (150, 3_000)
    assert catalog.overage_amount(cat["free"], 500) == (0, 0)
    s.billing_catalog = json.dumps({"growth": {"price": 2_999_00, "overage": 1_500}})
    s.billing_currency = "inr"
    assert catalog.plan("growth", s).price == 299_900 and catalog.plan("growth", s).included == 2_000
    assert catalog.currency(s) == "INR"


def test_signatures():
    rzp = Razorpay(KEY_ID, KEY_SECRET)
    good = hmac.new(KEY_SECRET.encode(), b"pay_1|sub_1", hashlib.sha256).hexdigest()
    assert rzp.checkout_signature_ok(payment_id="pay_1", subscription_id="sub_1", signature=good)
    assert not rzp.checkout_signature_ok(payment_id="pay_2", subscription_id="sub_1", signature=good)
    body = b'{"event":"x"}'
    assert webhook_signature_ok(body, _sign(body), HOOK_SECRET)
    assert not webhook_signature_ok(body + b" ", _sign(body), HOOK_SECRET)
    assert not webhook_signature_ok(body, _sign(body), "")


# ---- checkout, changes, webhooks, overage ---------------------------------------------------

def test_subscription_lifecycle_and_overage(fake):
    from app.main import app

    get_settings().billing_catalog = json.dumps({"growth": {"included": 3, "overage": 50}})
    with TestClient(app) as client:
        h, site = _tenant(client)
        # A plan remembered from another account / an earlier run is recreated.
        _sql("DELETE FROM razorpay_plans WHERE key_id = :k", k=KEY_ID)
        _sql("INSERT INTO razorpay_plans (key_id, plan, currency, amount, razorpay_plan_id) "
             "VALUES (:k, 'growth', 'USD', 39900, 'plan_gone')", k=KEY_ID)
        b = client.get("/tenant/billing", headers=h).json()
        assert b["plan"] == "free" and b["status"] == "none" and b["checkout_enabled"]
        assert b["usage"]["included"] == 100 and b["usage"]["capped"]

        assert client.post("/tenant/billing/checkout", json={"plan": "enterprise"},
                           headers=h).status_code == 422
        co = client.post("/tenant/billing/checkout", json={"plan": "growth"}, headers=h).json()
        assert co["action"] == "checkout" and co["key_id"] == KEY_ID and co["email"].endswith("@example.com")
        sub_id = co["subscription_id"]
        plan_amounts = {p["item"]["amount"] for p in fake.plans.values()}
        assert plan_amounts == {39_900}
        # Still Free until the payment is verified.
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "free"

        start = datetime.now(timezone.utc) - timedelta(days=29)
        fake.activate(sub_id, start)
        # Paid, but Checkout closed before reporting back and no webhook came:
        # opening the Billing page asks Razorpay and catches up.
        synced = client.get("/tenant/billing", headers=h).json()
        assert synced["plan"] == "growth" and synced["status"] == "active"
        bad = client.post("/tenant/billing/verify", headers=h, json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": sub_id,
            "razorpay_signature": "0" * 64})
        assert bad.status_code == 400
        sig = hmac.new(KEY_SECRET.encode(), f"pay_1|{sub_id}".encode(), hashlib.sha256).hexdigest()
        ok = client.post("/tenant/billing/verify", headers=h, json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": sub_id,
            "razorpay_signature": sig}).json()
        assert ok["plan"] == "growth" and ok["status"] == "active"
        assert ok["usage"]["included"] == 3 and not ok["usage"]["capped"]
        assert client.post("/tenant/billing/checkout", json={"plan": "growth"},
                           headers=h).status_code == 409

        # 5 conversations this cycle: 2 over the allowance of 3.
        _usage(site["site_key"], [f"s{i}" for i in range(5)], at=start + timedelta(days=1))
        now = client.get("/tenant/billing", headers=h).json()
        assert now["usage"]["conversations"] == 5 and now["usage"]["extra"] == 2
        assert now["usage"]["overage_amount"] == 100
        assert now["sites"][0]["conversations"] == 5

        # Renewal: the new cycle's charge bills last cycle's overage as an add-on.
        assert _webhook(client, "subscription.charged", fake.subs[sub_id],
                        secret_ok=False).status_code == 400
        renewed = dict(fake.activate(sub_id, start + timedelta(days=30)))
        renew_id = f"evt_renew_{uuid.uuid4().hex}"
        r = _webhook(client, "subscription.charged", renewed, event_id=renew_id).json()
        assert r["outcome"] == "subscription.charged"
        assert len(fake.addons) == 1 and fake.addons[0]["item"]["amount"] == 100
        assert fake.addons[0]["subscription_id"] == sub_id
        # Razorpay retries: the same event changes nothing.
        assert _webhook(client, "subscription.charged", renewed,
                        event_id=renew_id).json()["outcome"] == "duplicate"
        assert len(fake.addons) == 1
        hist = client.get("/tenant/billing", headers=h).json()["overage_history"]
        assert hist[0]["extra"] == 2 and hist[0]["addon_id"] == fake.addons[0]["id"]
        assert hist[0]["status"] == "addon"

        # Upgrade applies now; a downgrade waits for the cycle end.
        up = client.post("/tenant/billing/checkout", json={"plan": "scale"}, headers=h).json()
        assert up == {**up, "action": "changed", "effective": "now"}
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "scale"
        down = client.post("/tenant/billing/checkout", json={"plan": "growth"}, headers=h).json()
        assert down["effective"] == "cycle_end"
        b = client.get("/tenant/billing", headers=h).json()
        assert b["plan"] == "scale" and b["pending_plan"] == "growth"

        # Payment failures: retrying keeps the plan; halted falls back to Free.
        fake.subs[sub_id]["status"] = "pending"
        _webhook(client, "subscription.pending", fake.subs[sub_id])
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "scale"
        fake.subs[sub_id]["status"] = "halted"
        _webhook(client, "subscription.halted", fake.subs[sub_id])
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "free"

        # Cancel at the cycle end, then Razorpay's cancellation lands.
        fake.subs[sub_id]["status"] = "active"
        _webhook(client, "subscription.activated", fake.subs[sub_id])
        c = client.post("/tenant/billing/cancel", headers=h).json()
        assert c["cancel_at_cycle_end"] and c["plan"] in ("scale", "growth")
        fake.subs[sub_id]["status"] = "cancelled"
        _webhook(client, "subscription.cancelled", fake.subs[sub_id])
        final = client.get("/tenant/billing", headers=h).json()
        assert final["plan"] == "free" and final["status"] == "cancelled"

        # Another account's subscription events don't touch this one.
        assert _webhook(client, "subscription.charged", {"id": "sub_unknown", "status": "active"}
                        ).json()["outcome"] == "unknown_subscription"


def test_upi_subscription_overage_goes_by_payment_link(fake):
    """Razorpay refuses add-ons on UPI-autopay subscriptions: the period's
    overage is sent as a payment link, and its payment is recorded."""
    from app.main import app

    get_settings().billing_catalog = json.dumps({"growth": {"included": 1, "overage": 50}})
    with TestClient(app) as client:
        h, site = _tenant(client)
        sub_id = client.post("/tenant/billing/checkout", json={"plan": "growth"},
                             headers=h).json()["subscription_id"]
        start = datetime.now(timezone.utc) - timedelta(days=29)
        fake.activate(sub_id, start)
        fake.subs[sub_id]["payment_method"] = "upi"
        _webhook(client, "subscription.activated", fake.subs[sub_id])
        _usage(site["site_key"], ["u1", "u2", "u3", "u4"], at=start + timedelta(days=2))

        # Payment links are down at renewal: the period stays pending...
        fake.links_down = True
        _webhook(client, "subscription.charged", dict(fake.activate(sub_id, start + timedelta(days=30))))
        hist = client.get("/tenant/billing", headers=h).json()["overage_history"]
        assert hist[0]["status"] == "pending" and hist[0]["amount"] == 150
        assert fake.addons == [] and fake.links == []

        # ...and the next subscription event retries it, as a link this time.
        fake.links_down = False
        _webhook(client, "subscription.updated", fake.subs[sub_id])
        hist = client.get("/tenant/billing", headers=h).json()["overage_history"]
        assert hist[0]["status"] == "link" and hist[0]["payment_link_url"].startswith("https://")
        link = fake.links[0]
        assert link["amount"] == 150 and link["customer"]["email"].endswith("@example.com")
        assert link["notify"] == {"sms": False, "email": True} and len(link["reference_id"]) <= 40

        # Paid on Razorpay before any webhook arrives: the page catches up.
        link["status"] = "paid"
        assert client.get("/tenant/billing", headers=h).json()["overage_history"][0]["status"] == "paid"
        _sql("UPDATE billing_overage SET status = 'link' WHERE payment_link_id = :i", i=link["id"])
        link["status"] = "created"

        paid = {"entity": "event", "event": "payment_link.paid",
                "payload": {"payment_link": {"entity": {"id": link["id"], "status": "paid"}}}}
        body = json.dumps(paid).encode()
        r = client.post("/billing/razorpay/webhook", content=body, headers={
            "Content-Type": "application/json", "X-Razorpay-Signature": _sign(body)}).json()
        assert r["outcome"] == "overage_paid"
        assert client.get("/tenant/billing", headers=h).json()["overage_history"][0]["status"] == "paid"
        # Nothing is billed twice.
        _webhook(client, "subscription.updated", fake.subs[sub_id])
        assert len(fake.links) == 1


def _sign_checkout(payment_id: str, sub_id: str) -> str:
    return hmac.new(KEY_SECRET.encode(), f"{payment_id}|{sub_id}".encode(),
                    hashlib.sha256).hexdigest()


def test_upi_plan_change_is_scheduled_for_renewal(fake):
    """Razorpay can't change a UPI-Autopay subscription's plan: a new
    subscription starts at the renewal, its mandate approved now; the old one
    ends with the period, and the account hands over without a gap."""
    from app.main import app

    get_settings().billing_catalog = json.dumps({"growth": {"included": 1, "overage": 50}})
    with TestClient(app) as client:
        h, site = _tenant(client)
        old_id = client.post("/tenant/billing/checkout", json={"plan": "growth"},
                             headers=h).json()["subscription_id"]
        start = datetime.now(timezone.utc) - timedelta(days=20)
        fake.activate(old_id, start)
        fake.subs[old_id]["payment_method"] = "upi"
        _webhook(client, "subscription.activated", fake.subs[old_id])
        _usage(site["site_key"], ["v1", "v2", "v3"], at=start + timedelta(days=1))
        renewal = start + timedelta(days=30)

        co = client.post("/tenant/billing/checkout", json={"plan": "scale"}, headers=h).json()
        assert co["action"] == "checkout" and co["scheduled_for"].startswith(renewal.date().isoformat())
        new_id = co["subscription_id"]
        assert new_id != old_id and fake.subs[new_id]["start_at"] == int(renewal.timestamp())
        assert fake.subs[new_id]["notes"]["replaces"] == old_id
        b = client.get("/tenant/billing", headers=h).json()
        assert b["plan"] == "growth" and b["next"]["plan"] == "scale" and b["next"]["status"] == "created"
        # Not approved yet: choosing Scale again reopens the same mandate.
        again = client.post("/tenant/billing/checkout", json={"plan": "scale"}, headers=h).json()
        assert again["subscription_id"] == new_id

        # Approved in Checkout: verified, and the old subscription ends with the period.
        fake.subs[new_id]["status"] = "authenticated"
        ok = client.post("/tenant/billing/verify", headers=h, json={
            "razorpay_payment_id": "pay_auth", "razorpay_subscription_id": new_id,
            "razorpay_signature": _sign_checkout("pay_auth", new_id)}).json()
        assert ok["plan"] == "growth" and ok["next"]["status"] == "authenticated"
        assert ok["cancel_at_cycle_end"] and fake.subs[old_id].get("cancel_scheduled")
        assert client.post("/tenant/billing/checkout", json={"plan": "growth"},
                           headers=h).status_code == 409

        # The renewal: the old one's cancellation doesn't drop the account to Free...
        fake.subs[old_id]["status"] = "cancelled"
        _webhook(client, "subscription.cancelled", fake.subs[old_id])
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "growth"
        # ...and the new one's first charge hands over and bills the old cycle.
        fake.activate(new_id, renewal)
        fake.subs[new_id]["payment_method"] = "upi"
        _webhook(client, "subscription.charged", fake.subs[new_id])
        b = client.get("/tenant/billing", headers=h).json()
        assert b["plan"] == "scale" and b["status"] == "active" and b["next"] is None
        assert not b["cancel_at_cycle_end"]
        hist = b["overage_history"][0]
        assert hist["extra"] == 2 and hist["status"] == "link"   # UPI: by payment link
        # Late events for the retired subscription change nothing.
        _webhook(client, "subscription.completed", {**fake.subs[old_id], "status": "completed"})
        assert client.get("/tenant/billing", headers=h).json()["plan"] == "scale"


def test_scheduled_switch_hands_over_without_webhooks(fake):
    """No webhooks (e.g. a laptop): the Billing page notices the approval and,
    after the renewal, the handover — and still bills the old cycle."""
    from app.main import app

    get_settings().billing_catalog = json.dumps({"growth": {"included": 1, "overage": 50}})
    with TestClient(app) as client:
        h, site = _tenant(client)
        old_id = client.post("/tenant/billing/checkout", json={"plan": "growth"},
                             headers=h).json()["subscription_id"]
        start = datetime.now(timezone.utc) - timedelta(days=20)
        fake.activate(old_id, start)
        fake.subs[old_id]["payment_method"] = "upi"
        client.post("/tenant/billing/verify", headers=h, json={
            "razorpay_payment_id": "pay_1", "razorpay_subscription_id": old_id,
            "razorpay_signature": _sign_checkout("pay_1", old_id)})
        _usage(site["site_key"], ["w1", "w2"], at=start + timedelta(days=1))
        new_id = client.post("/tenant/billing/checkout", json={"plan": "scale"},
                             headers=h).json()["subscription_id"]

        fake.subs[new_id]["status"] = "authenticated"   # approved; Checkout closed early
        b = client.get("/tenant/billing", headers=h).json()
        assert b["next"]["status"] == "authenticated" and fake.subs[old_id].get("cancel_scheduled")

        # The renewal passes with no webhook at all.
        renewal = datetime.now(timezone.utc) - timedelta(minutes=5)
        _sql("UPDATE tenant_billing SET current_end = :e WHERE subscription_id = :s",
             e=renewal, s=old_id)
        fake.subs[old_id]["status"] = "cancelled"
        fake.activate(new_id, renewal)
        b = client.get("/tenant/billing", headers=h).json()
        assert b["plan"] == "scale" and b["next"] is None
        assert b["overage_history"][0]["extra"] == 1


def test_abandoned_switch_is_dropped_on_cancel(fake):
    from app.main import app

    with TestClient(app) as client:
        h, _ = _tenant(client)
        old_id = client.post("/tenant/billing/checkout", json={"plan": "growth"},
                             headers=h).json()["subscription_id"]
        fake.activate(old_id, datetime.now(timezone.utc) - timedelta(days=3))
        fake.subs[old_id]["payment_method"] = "upi"
        client.post("/tenant/billing/verify", headers=h, json={
            "razorpay_payment_id": "pay_2", "razorpay_subscription_id": old_id,
            "razorpay_signature": _sign_checkout("pay_2", old_id)})
        new_id = client.post("/tenant/billing/checkout", json={"plan": "scale"},
                             headers=h).json()["subscription_id"]
        c = client.post("/tenant/billing/cancel", headers=h).json()
        assert c["next"] is None and c["cancel_at_cycle_end"]
        assert fake.subs[new_id]["status"] == "cancelled"        # mandate withdrawn
        assert fake.subs[old_id].get("cancel_scheduled")          # current ends with the period


def test_billing_needs_keys_for_checkout():
    from app.main import app

    with TestClient(app) as client:
        h, _ = _tenant(client)
        b = client.get("/tenant/billing", headers=h).json()
        assert b["checkout_enabled"] is False and b["key_id"] is None
        r = client.post("/tenant/billing/checkout", json={"plan": "growth"}, headers=h)
        assert r.status_code == 503
        assert client.get("/tenant/billing").status_code == 401


# ---- the Free cap on public turns ---------------------------------------------------------------

def test_free_plan_caps_new_conversations():
    from app.main import app

    get_settings().billing_catalog = json.dumps({"free": {"included": 2}})
    with TestClient(app) as client:
        h, site = _tenant(client)
        _usage(site["site_key"], ["old-1", "old-2"])
        new = client.post("/chat", json={"message": "hello", "key": site["public_key"]})
        assert new.status_code == 429 and new.json()["detail"] == "plan_limit_reached"
        # A conversation already under way may finish.
        going = client.post("/chat", json={"message": "and pricing?", "key": site["public_key"],
                                           "session_id": "old-1"})
        assert going.status_code == 200
        b = client.get("/tenant/billing", headers=h).json()
        assert b["usage"]["limit_reached"] is True

        # The voice socket refuses the same way, and says why.
        with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text", "payload": {"text": "hi"}})
            for _ in range(20):
                env = ws.receive_json()
                if env["type"] == "error":
                    assert env["payload"]["reason"] == "plan_limit_reached"
                    assert "not available" in env["payload"]["message"]
                    break
            else:
                pytest.fail("no refusal")


def test_analytics_reports_cost_per_conversation():
    from app.main import app

    with TestClient(app) as client:
        h, site = _tenant(client)
        _usage(site["site_key"], ["a", "b", "b", "c"])  # b had two turns
        perf = client.get(f"/tenant/websites/{site['id']}/analytics", headers=h).json()["performance"]
        assert perf["conversations"] == 3
        total = client.get(f"/tenant/websites/{site['id']}/analytics", headers=h).json()["totals"]["total_cost"]
        assert perf["cost_per_conversation"] == pytest.approx(total / 3, rel=1e-3)
