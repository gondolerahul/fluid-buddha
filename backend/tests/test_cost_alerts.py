"""
Per-site cost alerts (F-3): a site's own daily threshold and the daily spend
cap each raise one alert a day, posted to the site's Slack and listed in the
console, without ever delaying a visitor's turn.
"""
from __future__ import annotations

import time
import uuid

import httpx
from fastapi.testclient import TestClient

from app.analytics import alerts
from app.leads import delivery
from app.main import app

SLACK = "https://hooks.slack.com/services/T/B/X"


def test_which_alerts_are_due():
    assert alerts.due(0.5, 0, None) == []
    assert alerts.due(0.5, 0, 1.0) == []
    assert alerts.due(1.0, 0, 1.0) == [("threshold", 1.0)]
    assert alerts.due(7.9, 10, None) == []
    assert alerts.due(8.0, 10, None) == [("cap_80", 10)]
    assert alerts.due(12, 10, 1.0) == [("threshold", 1.0), ("cap_80", 10), ("cap_100", 10)]
    assert "80%" in alerts.message("Acme", "cap_80", 8, 10)
    assert "paused" in alerts.message("Acme", "cap_100", 10, 10)


def _wait_for(client: TestClient, url: str, headers: dict, count: int) -> list[dict]:
    """Alerts are sent in the background: poll the console list briefly."""
    rows: list[dict] = []
    for _ in range(50):
        rows = client.get(url, headers=headers).json()
        if len(rows) >= count and all(r["delivered"] or r["error"] for r in rows):
            return rows
        time.sleep(0.05)
    return rows


def test_threshold_and_cap_alerts_go_to_slack_once_a_day(monkeypatch):
    monkeypatch.setattr(delivery, "RETRY_DELAYS", (0, 0))
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(alerts, "_transport", httpx.MockTransport(handler))
    with TestClient(app) as client:
        tok = client.post("/auth/register", json={
            "email": f"ca_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        site = client.post("/tenant/websites", json={"name": "Cost Co"}, headers=h).json()
        base = f"/tenant/websites/{site['id']}"

        bad = client.put(f"{base}/integrations", headers=h, json={"cost_alert_usd": -1})
        assert bad.status_code == 422
        cfg = client.put(f"{base}/integrations", headers=h, json={
            "slack_webhook_url": SLACK, "cost_alert_usd": 1e-9}).json()
        assert cfg["cost_alert_usd"] == 1e-9
        assert client.get(f"{base}/integrations", headers=h).json()["cost_alert_usd"] == 1e-9

        # Nothing spent before the first turn: no alert. The turn records a cost.
        chat = {"message": "hello", "key": site["public_key"]}
        assert client.post("/chat", json=chat).status_code == 200
        assert client.get(f"{base}/cost-alerts", headers=h).json() == []
        # The next turn sees today's cost past the threshold: one alert.
        assert client.post("/chat", json=chat).status_code == 200
        rows = _wait_for(client, f"{base}/cost-alerts", h, 1)
        assert [r["level"] for r in rows] == ["threshold"] and rows[0]["delivered"]
        assert len(sent) == 1 and sent[0].url.host == "hooks.slack.com"
        assert b"Cost Co" in sent[0].content
        # Further turns the same day don't repeat it.
        client.post("/chat", json=chat)
        time.sleep(0.2)
        assert len(client.get(f"{base}/cost-alerts", headers=h).json()) == 1 and len(sent) == 1

        # A daily cap: 80 % and 100 % alerts, and the turn is refused.
        app.state.runtime.settings.public_daily_spend_cap_usd = 1e-9
        r = client.post("/chat", json=chat)
        assert r.status_code == 429
        rows = _wait_for(client, f"{base}/cost-alerts", h, 3)
        assert sorted(r["level"] for r in rows) == ["cap_100", "cap_80", "threshold"]
        assert len(sent) == 3

        app.state.runtime.settings.public_daily_spend_cap_usd = 0

        # Another tenant can't read them.
        tok2 = client.post("/auth/register", json={
            "email": f"ca_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        assert client.get(f"{base}/cost-alerts",
                          headers={"Authorization": f"Bearer {tok2}"}).status_code == 404


def test_no_alert_work_without_a_threshold_or_cap(monkeypatch):
    called = []
    monkeypatch.setattr(alerts, "schedule", lambda *a: called.append(a))
    with TestClient(app) as client:
        site = f"noalert-{uuid.uuid4().hex[:8]}"
        app.state.runtime.settings.public_daily_spend_cap_usd = 0
        client.post("/chat", json={"message": "hello", "site": site})
        client.post("/chat", json={"message": "again", "site": site})
    assert called == []
