"""
Experimentation engine (M2-4): N-variant tests of the greeting, triggers, tour,
persona and design level — the statistics, assignment, the console flow, and
the variant reaching the conversation.
"""
from __future__ import annotations

import json
import random
import uuid

import pytest
from fastapi.testclient import TestClient

from app.experiments.stats import sample_size_arms, split_alpha, variant_verdict
from app.experiments.store import assign_arm, clean_variants


# ---- statistics ---------------------------------------------------------------

def test_split_alpha_and_planner():
    assert split_alpha(2) == pytest.approx(0.05)
    assert split_alpha(4) == pytest.approx(0.05 / 3)
    two = sample_size_arms(0.05, 0.3, 2)
    three = sample_size_arms(0.05, 0.3, 3)
    assert two and three
    # More variants: more arms to fill and a stricter budget per comparison.
    assert three["per_variant"] > two["per_variant"]
    assert three["total"] >= 3 * three["per_variant"] and three["holdout"] == 0
    held = sample_size_arms(0.05, 0.3, 3, holdout_share=0.2)
    assert held["per_variant"] == three["per_variant"] and held["holdout"] > 0
    assert held["total"] == pytest.approx(held["per_variant"] * 3 / 0.8, abs=1)
    assert sample_size_arms(0.05, 0.3, 1) is None
    assert sample_size_arms(0.9, 0.3, 3) is None


def test_variant_verdict():
    # Not enough yet.
    early = variant_verdict([("a", 20, 2), ("b", 20, 3), ("c", 20, 1)])
    assert early["status"] == "keep_running" and early["winner"] is None
    # c clearly beats the control; b is level with it.
    clear = variant_verdict([("a", 3000, 150), ("b", 3000, 155), ("c", 3000, 330)])
    assert clear["status"] == "winner" and clear["winner"] == "c"
    assert clear["comparisons"]["c"]["status"] == "significant"
    assert clear["comparisons"]["b"]["status"] != "significant"
    # The control beats every variant: it wins.
    ctrl = variant_verdict([("a", 3000, 330), ("b", 3000, 140), ("c", 3000, 150)])
    assert ctrl["status"] == "winner" and ctrl["winner"] == "a"
    # Planned sample in, nothing separated.
    flat = variant_verdict([("a", 3000, 150), ("b", 3000, 152)], plan_reached=True)
    assert flat["status"] == "no_difference"


def test_false_wins_stay_under_five_percent_with_three_variants_and_peeking():
    """No variant is better; the results are read after every 300 visitors.
    The chance that the run ever names a winner stays at or under 5 %."""
    rng = random.Random(11)
    runs, false_wins = 200, 0
    for _ in range(runs):
        n = {"a": 0, "b": 0, "c": 0}
        x = {"a": 0, "b": 0, "c": 0}
        won = False
        for i in range(1, 9_001):
            k = "abc"[rng.randrange(3)]
            n[k] += 1
            x[k] += rng.random() < 0.05
            if i % 300 == 0:
                v = variant_verdict([(a, n[a], x[a]) for a in "abc"])
                if v["status"] == "winner":
                    won = True
                    break
        false_wins += won
    assert false_wins / runs <= 0.05


def test_a_real_lift_is_found():
    rng = random.Random(5)
    found = 0
    for _ in range(40):
        n = {"a": 0, "b": 0, "c": 0}
        x = {"a": 0, "b": 0, "c": 0}
        rate = {"a": 0.05, "b": 0.05, "c": 0.10}
        for _ in range(9_000):
            k = "abc"[rng.randrange(3)]
            n[k] += 1
            x[k] += rng.random() < rate[k]
        v = variant_verdict([(a, n[a], x[a]) for a in "abc"])
        found += v["winner"] == "c"
    assert found >= 32   # 80 %+ power at a doubled rate on 3000 per arm


def test_assignment_splits_variants_evenly_after_the_holdout():
    exp = uuid.uuid4()
    arms = [assign_arm(exp, f"visitor-{i:06d}", 10, ["a", "b", "c"]) for i in range(30_000)]
    assert 0.09 < arms.count("holdout") / len(arms) < 0.11
    for k in "abc":
        assert 0.28 < arms.count(k) / len(arms) < 0.32
    assert assign_arm(exp, "visitor-000007", 10, ["a", "b", "c"]) == arms[7]
    no_hold = [assign_arm(exp, f"v-{i:08d}", 0, ["a", "b"]) for i in range(2000)]
    assert "holdout" not in no_hold and 0.45 < no_hold.count("a") / 2000 < 0.55


def test_variant_validation():
    site = {"personas": ["cfo", "engineer"], "rule_ids": ["r1", "r2"]}
    ok = clean_variants("greeting", [{"overrides": {"greeting": " Hi! "}},
                                     {"label": "Short", "overrides": {"greeting": "Hey"}}], **site)
    assert [v["key"] for v in ok] == ["a", "b"] and ok[0]["label"] == "Control"
    assert ok[0]["overrides"] == {"greeting": "Hi!"}
    assert clean_variants("trigger", [{"overrides": {"triggers": []}},
                                      {"overrides": {"triggers": ["r2", "r1"]}}], **site)[1][
        "overrides"] == {"triggers": ["r1", "r2"]}
    assert clean_variants("persona", [{"overrides": {"persona": ""}},
                                      {"overrides": {"persona": "cfo"}}], **site)
    for subject, variants in (
        ("greeting", [{"overrides": {"greeting": "Hi"}}]),                                  # one
        ("greeting", [{"overrides": {"greeting": "Hi"}}, {"overrides": {"greeting": "Hi"}}]),  # same
        ("greeting", [{"overrides": {"greeting": ""}}, {"overrides": {"greeting": "Hi"}}]),
        ("trigger", [{"overrides": {"triggers": ["nope"]}}, {"overrides": {"triggers": []}}]),
        ("persona", [{"overrides": {"persona": "ceo"}}, {"overrides": {"persona": ""}}]),
        ("design", [{"overrides": {"design": "level9"}}, {"overrides": {"design": "level1"}}]),
        ("tour", [{"overrides": {"tour": "yes"}}, {"overrides": {"tour": False}}]),
        ("price", [{"overrides": {}}, {"overrides": {}}]),
    ):
        with pytest.raises(ValueError):
            clean_variants(subject, variants, **site)


# ---- the flow, end to end -------------------------------------------------------

def _tenant(client: TestClient) -> dict:
    email = f"var_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register",
                      json={"email": email, "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _beacon(client: TestClient, path: str, body: dict):
    return client.post(path, content=json.dumps(body), headers={"Content-Type": "text/plain"})


GREETINGS = ["Hi! Ask me anything about our plans.",
             "Welcome — want a 60-second tour?",
             "Hello! I can work out which plan fits your team."]


def test_three_greeting_test_finds_a_winner_and_promotes_it():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Greet Co"}, headers=h).json()
        wid, key = site["id"], site["public_key"]
        base = f"/tenant/websites/{wid}/tests"

        assert client.get(base, headers=h).json() == {"tests": [], "holdout_running": False}
        # No test yet: no arm, and no site greeting either.
        off = _beacon(client, "/experiment/enroll", {"key": key, "visitor": "visitor-zzzz"}).json()
        assert off["arm"] is None and off["overrides"] == {}
        assert off["defaults"] == {"greeting": None, "design": "level1", "accent": None,
                                   "languages": ["en"],
                                   "widget_language": "auto", "greeting_hi": None,
                                   "starters": []}

        plan = client.get(f"{base}/plan", params={"variants": 3, "baseline": 0.05, "mde": 0.5},
                          headers=h).json()
        assert plan["needed"]["per_variant"] > 0

        # A holdout run is going: starting a test replaces it (one at a time).
        client.put(f"/tenant/websites/{wid}/experiment", json={"enabled": True}, headers=h)
        assert client.get(base, headers=h).json()["holdout_running"] is True

        bad = client.post(base, json={"name": "Dupes", "subject": "greeting", "variants": [
            {"overrides": {"greeting": "Same"}}, {"overrides": {"greeting": "Same"}}]}, headers=h)
        assert bad.status_code == 422
        started = client.post(base, json={
            "name": "Opening line", "subject": "greeting", "goal_path": "/signup",
            "variants": [{"label": "Plans", "overrides": {"greeting": GREETINGS[0]}},
                         {"label": "Tour", "overrides": {"greeting": GREETINGS[1]}},
                         {"label": "Fit", "overrides": {"greeting": GREETINGS[2]}}]}, headers=h)
        assert started.status_code == 201, started.text
        test = started.json()
        tid = test["id"]
        assert test["subject"] == "greeting" and [v["key"] for v in test["variants"]] == ["a", "b", "c"]
        holdout = client.get(f"/tenant/websites/{wid}/experiment", headers=h).json()
        assert holdout["status"] == "stopped"
        # ...and the holdout can't be switched back on while the test runs.
        assert client.put(f"/tenant/websites/{wid}/experiment", json={"enabled": True},
                          headers=h).status_code == 409

        arms: dict[str, list[str]] = {"a": [], "b": [], "c": []}
        for i in range(900):
            v = f"visitor-{i:05d}"
            r = _beacon(client, "/experiment/enroll", {"key": key, "visitor": v}).json()
            assert r["experiment_id"] == tid and r["goal_path"] == "/signup"
            assert r["overrides"] == {"greeting": GREETINGS["abc".index(r["arm"])]}
            arms[r["arm"]].append(v)
        assert all(250 < len(vs) < 350 for vs in arms.values())

        # "Fit" converts at 40 %, the others at 10 %.
        for k, vs in arms.items():
            rate = 0.4 if k == "c" else 0.1
            for i, v in enumerate(vs):
                if i < int(len(vs) * rate):
                    assert _beacon(client, "/experiment/convert", {
                        "key": key, "visitor": v, "experiment_id": tid, "name": "goal_page"}).json()["counted"]

        res = client.get(f"{base}/{tid}", headers=h).json()
        assert res["verdict"]["status"] == "winner" and res["verdict"]["winner"] == "c"
        assert res["verdict"]["alpha"] == pytest.approx(0.025)
        by = {v["key"]: v for v in res["variants"]}
        assert by["c"]["vs_control"]["status"] == "significant"
        assert by["a"]["vs_control"] is None and by["a"]["visitors"] == len(arms["a"])
        assert res["holdout"] is None and res["plan"]["visitors_so_far"] == 900

        listed = client.get(base, headers=h).json()["tests"]
        assert listed[0]["id"] == tid and listed[0]["visitors"] == 900

        # Promote the winner: it becomes the site's greeting, and the test ends.
        assert client.post(f"{base}/{tid}/promote", json={"variant": "e"}, headers=h).status_code == 422
        done = client.post(f"{base}/{tid}/promote", json={"variant": "c"}, headers=h).json()
        assert done["winner"] == "c" and done["status"] == "stopped" and done["promoted_at"]
        prof = client.get(f"/tenant/websites/{wid}/profile", headers=h).json()
        assert prof["greeting"] == GREETINGS[2]
        after = _beacon(client, "/experiment/enroll", {"key": key, "visitor": "visitor-new-01"}).json()
        assert after["arm"] is None and after["defaults"]["greeting"] == GREETINGS[2]

        # Other tenants can't see or touch it.
        h2 = _tenant(client)
        assert client.get(f"{base}/{tid}", headers=h2).status_code == 404
        assert client.post(f"{base}/{tid}/promote", json={"variant": "a"}, headers=h2).status_code == 404


def test_trigger_tour_and_design_tests_promote_their_settings():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Promo Co"}, headers=h).json()
        wid = site["id"]
        base = f"/tenant/websites/{wid}/tests"
        rule = {"name": "Dwell", "enabled": True, "kind": "time_on_page", "seconds": 20, "pages": [],
                "message": "Need a hand?", "action": "nudge", "max_per_day": 1, "priority": 50}
        r1 = client.post(f"/tenant/websites/{wid}/triggers", json=rule, headers=h).json()["id"]
        r2 = client.post(f"/tenant/websites/{wid}/triggers", json={**rule, "name": "Exit",
                         "kind": "exit_intent"}, headers=h).json()["id"]

        t = client.post(base, json={"name": "Which nudge", "subject": "trigger", "holdout_pct": 10,
                                    "variants": [{"overrides": {"triggers": [r1]}},
                                                 {"overrides": {"triggers": [r2]}},
                                                 {"overrides": {"triggers": []}}]}, headers=h)
        assert t.status_code == 201, t.text
        tid = t.json()["id"]
        res = client.get(f"{base}/{tid}", headers=h).json()
        assert res["holdout"] is not None and res["verdict"]["status"] == "keep_running"
        client.post(f"{base}/{tid}/promote", json={"variant": "b"}, headers=h)
        rules = {r["id"]: r["enabled"] for r in
                 client.get(f"/tenant/websites/{wid}/triggers", headers=h).json()["rules"]}
        assert rules == {r1: False, r2: True}

        t = client.post(base, json={"name": "Tour or not", "subject": "tour", "variants": [
            {"overrides": {"tour": True}}, {"overrides": {"tour": False}}]}, headers=h).json()
        client.post(f"{base}/{t['id']}/promote", json={"variant": "b"}, headers=h)
        assert client.get(f"/tenant/websites/{wid}/profile", headers=h).json()["tour_enabled"] is False

        t = client.post(base, json={"name": "Look", "subject": "design", "variants": [
            {"overrides": {"design": "level1"}}, {"overrides": {"design": "level2"}}]}, headers=h).json()
        stopped = client.post(f"{base}/{t['id']}/stop", headers=h).json()
        assert stopped["status"] == "stopped" and stopped["winner"] is None
        client.post(f"{base}/{t['id']}/promote", json={"variant": "b"}, headers=h)
        assert client.get(f"/tenant/websites/{wid}", headers=h).json()["design"] == "level2"


def test_the_variant_reaches_the_conversation():
    """The voice greeting is the variant's text, spoken as written; the text
    chat starts in the variant's persona."""
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Talk Co"}, headers=h).json()
        wid, key = site["id"], site["public_key"]
        client.put(f"/tenant/websites/{wid}/profile", json={"personas": [
            {"slug": "cfo", "label": "Finance lead"}, {"slug": "dev", "label": "Engineer"}]}, headers=h)
        base = f"/tenant/websites/{wid}/tests"

        t = client.post(base, json={"name": "Hello", "subject": "greeting", "variants": [
            {"overrides": {"greeting": "Hello from A."}},
            {"overrides": {"greeting": "Hello from B."}}]}, headers=h).json()

        def opener(exp: dict | None) -> str:
            with client.websocket_connect(f"/ws/voice?key={key}") as ws:
                assert ws.receive_json()["type"] == "ready"
                payload = {"page": "/", **({"exp": exp} if exp else {})}
                ws.send_json({"channel": "EVENTS", "type": "hello", "payload": payload})
                for _ in range(100):
                    e = ws.receive_json()
                    if e["channel"] == "AUDIO" and e["type"] == "start":
                        return e["payload"]["text"]
            raise AssertionError("no welcome")

        assert opener({"id": t["id"], "arm": "b"}) == "Hello from B."
        assert opener({"id": t["id"], "arm": "a"}) == "Hello from A."
        # A made-up variant or test id gets the ordinary (model-written) welcome.
        assert opener({"id": str(uuid.uuid4()), "arm": "b"}) not in ("Hello from A.", "Hello from B.")

        client.post(f"{base}/{t['id']}/stop", headers=h)
        p = client.post(base, json={"name": "Who", "subject": "persona", "variants": [
            {"overrides": {"persona": ""}}, {"overrides": {"persona": "cfo"}}]}, headers=h).json()
        chat = client.post("/chat", json={"message": "what does it cost?", "key": key,
                                          "exp": {"id": p["id"], "arm": "b"}}).json()
        assert chat["persona"] == "cfo"
        # The promoted persona is where every new conversation starts.
        client.post(f"{base}/{p['id']}/promote", json={"variant": "b"}, headers=h)
        plain = client.post("/chat", json={"message": "what does it cost?", "key": key}).json()
        assert plain["persona"] == "cfo"
