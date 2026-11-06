"""M2-3 proactive triggers: rule validation, the widget's view, event counting
and the console's per-rule numbers."""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.triggers.store import RuleIn

from tests.test_teams import _register


def _beacon(client, body, ua=None):
    headers = {"Content-Type": "text/plain"}
    if ua:
        headers["User-Agent"] = ua
    return client.post("/widget/triggers/event", content=json.dumps(body), headers=headers)


def test_rule_validation_and_defaults():
    r = RuleIn(name="Pricing", kind="time_on_page", pages=[" /pricing* ", ""], message="Questions?")
    assert r.seconds == 20 and r.pages == ["/pricing*"] and r.params() == {"seconds": 20}
    assert RuleIn(name="Back", kind="return_visit", message="Welcome back").params() == {
        "visits": 2, "within_days": 30}
    assert RuleIn(name="Exit", kind="exit_intent", message="Before you go").params() == {}
    for bad in ({"pages": ["pricing"]}, {"pages": ["/a?b=1"]}, {"seconds": 1},
                {"message": ""}, {"kind": "hover"}, {"max_per_day": 0}):
        with pytest.raises(ValidationError):
            RuleIn(**{"name": "x", "kind": "time_on_page", "message": "hi", **bad})


def test_rules_reach_the_widget_and_events_are_counted():
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Nudge Co"}, headers=h).json()
        base = f"/tenant/websites/{site['id']}/triggers"
        key = site["public_key"]

        pricing = client.post(base, headers=h, json={
            "name": "Pricing dwell", "kind": "time_on_page", "seconds": 15, "pages": ["/pricing"],
            "message": "Want help choosing a plan?", "priority": 80}).json()
        paused = client.post(base, headers=h, json={
            "name": "Exit", "kind": "exit_intent", "message": "Before you go…", "enabled": False}).json()
        assert client.post(base, headers=h, json={"name": "bad", "kind": "scroll_depth",
                                                  "percent": 500, "message": "x"}).status_code == 422

        # The widget only sees enabled rules, without names.
        seen = client.get("/widget/triggers", params={"key": key}).json()["rules"]
        assert [r["id"] for r in seen] == [pricing["id"]]
        assert seen[0] == {"id": pricing["id"], "kind": "time_on_page", "seconds": 15,
                           "pages": ["/pricing"], "message": "Want help choosing a plan?",
                           "compose": False, "action": "nudge", "max_per_day": 1, "priority": 80}
        assert client.get("/widget/triggers", params={"key": "fbk_nope"}).status_code == 403

        # Events: distinct visitors per event; capped per day; bots and other rules ignored.
        rid = pricing["id"]
        for i in range(10):
            v = f"visitor-{i:04d}"
            assert _beacon(client, {"key": key, "visitor": v, "rule_id": rid, "event": "shown",
                                    "page": "/pricing"}).json()["counted"]
            if i < 4:
                _beacon(client, {"key": key, "visitor": v, "rule_id": rid, "event": "clicked"})
            if i < 2:
                _beacon(client, {"key": key, "visitor": v, "rule_id": rid, "event": "engaged"})
            if i == 9:
                _beacon(client, {"key": key, "visitor": v, "rule_id": rid, "event": "dismissed"})
        counted = [_beacon(client, {"key": key, "visitor": "visitor-0000", "rule_id": rid,
                                    "event": "shown"}).json()["counted"] for _ in range(6)]
        assert counted.count(True) == 4          # 5 a day per visitor, rule and event
        assert not _beacon(client, {"key": key, "visitor": "visitor-bot1", "rule_id": rid,
                                    "event": "shown"}, ua="Googlebot/2.1").json()["counted"]
        assert not _beacon(client, {"key": key, "visitor": "visitor-0001", "rule_id": str(uuid.uuid4()),
                                    "event": "shown"}).json()["counted"]
        assert _beacon(client, {"key": key, "visitor": "visitor-0001", "rule_id": rid,
                                "event": "hovered"}).status_code == 422

        rules = {r["id"]: r for r in client.get(base, headers=h).json()["rules"]}
        st = rules[rid]["stats"]
        assert (st["shown"], st["clicked"], st["engaged"], st["dismissed"]) == (10, 4, 2, 1)
        assert st["click_rate"] == pytest.approx(0.4) and st["engage_rate"] == pytest.approx(0.2)
        assert rules[paused["id"]]["stats"] is None

        # Edit and delete.
        upd = client.put(f"{base}/{paused['id']}", headers=h, json={
            "name": "Exit", "kind": "exit_intent", "message": "Before you go — any questions?",
            "action": "open"}).json()
        assert upd["enabled"] and upd["action"] == "open"
        assert len(client.get("/widget/triggers", params={"key": key}).json()["rules"]) == 2
        assert client.delete(f"{base}/{rid}", headers=h).status_code == 204
        assert client.delete(f"{base}/{rid}", headers=h).status_code == 404

        # Another account can't touch them.
        other_h, _ = _register(client)
        assert client.get(base, headers=other_h).status_code == 404


def test_trigger_reads_respect_the_site_domain():
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Dom T", "domain": "domt.example"},
                           headers=h).json()
        from app.config import get_settings
        get_settings().app_env = "production"   # restored by conftest
        r = client.get("/widget/triggers", params={"key": site["public_key"]},
                       headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        ok = client.get("/widget/triggers", params={"key": site["public_key"]},
                        headers={"Origin": "https://domt.example"})
        assert ok.status_code == 200 and ok.json() == {"rules": []}
