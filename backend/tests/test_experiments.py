"""
Holdout A/B (WS11): the statistics, arm assignment, and the experiment flow
through the public widget endpoints and the console API.
"""
from __future__ import annotations

import uuid

import pytest
from unittest.mock import ANY

from fastapi.testclient import TestClient

from app.experiments.bots import is_bot
from app.experiments.stats import (
    lift, newcombe_diff, relative_lift, sample_size, sequential_diff, two_proportion_p, wilson,
)
from app.experiments.store import assign_arm, clean_goal_path


# ---- statistics ---------------------------------------------------------------

def test_wilson_and_newcombe_match_published_values():
    # Newcombe (1998), Statistics in Medicine 17:873, example (a): 56/70 vs 48/80.
    d, low, high = newcombe_diff(56, 70, 48, 80)
    assert d == pytest.approx(0.2)
    assert low == pytest.approx(0.0524, abs=5e-4)
    assert high == pytest.approx(0.3339, abs=5e-4)
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=5e-4)


def test_lift_status_and_relative_interval():
    # Not enough visitors yet: report the numbers but call it collecting.
    early = lift(3, 20, 1, 10)
    assert early.status == "collecting" and early.diff is not None
    # A clear effect: 12 % vs 5 % with 2000 / 500 visitors.
    clear = lift(240, 2000, 25, 500)
    assert clear.status == "significant"
    assert clear.diff == pytest.approx(0.07) and clear.diff_low > 0
    assert clear.relative == pytest.approx(1.4) and clear.relative_low > 0
    assert clear.p_value < 0.001
    # Identical rates: no effect.
    same = lift(100, 1000, 10, 100)
    assert same.status == "not_significant" and same.diff == pytest.approx(0.0)
    assert same.diff_low < 0 < same.diff_high
    assert two_proportion_p(100, 1000, 10, 100) == pytest.approx(1.0)
    # No holdout conversions: the ratio is unbounded, the difference still works.
    assert relative_lift(5, 100, 0, 100) is None
    assert lift(0, 50, 0, 50).status == "collecting"
    assert lift(5, 50, 3, 50).status == "collecting"      # fewer than 10 conversions


def test_peeking_guard_reports_trending_until_the_always_valid_interval_agrees():
    # 6 % vs 4 % on 3000 / 1000 visitors: the fixed-horizon interval excludes
    # zero (p ~ 0.02) but a test read every day can't call that yet.
    early = lift(180, 3000, 40, 1000)
    assert early.diff_low > 0 and early.p_value < 0.05
    assert early.seq_low < 0 < early.seq_high
    assert early.status == "trending"
    # The same rates on ten times the traffic: now a finding.
    later = lift(1800, 30000, 400, 10000)
    assert later.status == "significant" and later.seq_low > 0
    # The always-valid interval is always the wider one.
    assert later.seq_low < later.diff_low and later.seq_high > later.diff_high
    assert sequential_diff(0, 100, 0, 100) is None


def test_always_valid_interval_keeps_false_wins_down_when_peeking():
    # No real effect, read after every 200 visitors: the fixed-horizon interval
    # "wins" far more often than 5 %, the always-valid one doesn't.
    import random
    rng = random.Random(7)
    runs, seq_wins, naive_wins = 120, 0, 0
    for _ in range(runs):
        xa = na = xh = nh = 0
        seq = naive = False
        for i in range(1, 10_001):
            if rng.random() < 0.2:
                nh += 1
                xh += rng.random() < 0.05
            else:
                na += 1
                xa += rng.random() < 0.05
            if i % 200 == 0:
                st = lift(xa, na, xh, nh).status
                seq |= st == "significant"
                naive |= st in ("significant", "trending")
        seq_wins += seq
        naive_wins += naive
    assert seq_wins / runs <= 0.08
    assert naive_wins > 2 * seq_wins


def test_sample_size_planner():
    small = sample_size(0.05, 0.5, 0.2)
    assert small and small["total"] == small["holdout"] + small["agent"]
    assert 0.19 < small["holdout"] / small["total"] < 0.21
    # Smaller effects, rarer goals and smaller holdouts all need more visitors.
    assert sample_size(0.05, 0.2, 0.2)["total"] > small["total"]
    assert sample_size(0.02, 0.5, 0.2)["total"] > small["total"]
    assert sample_size(0.05, 0.5, 0.1)["total"] > small["total"]
    assert sample_size(0.0, 0.5, 0.2) is None and sample_size(0.8, 0.5, 0.2) is None


def test_bot_detection():
    chrome = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    assert not is_bot(chrome)
    assert not is_bot("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                      "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
    assert is_bot(chrome, automated=True)
    assert not is_bot(chrome, automated="true")   # only a real boolean counts
    for ua in ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
               "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
               "HeadlessChrome/130.0.0.0 Safari/537.36",
               "curl/8.4.0", "python-requests/2.32", "facebookexternalhit/1.1",
               "Mozilla/5.0 (compatible; UptimeRobot/2.0)", "", None):
        assert is_bot(ua), ua


def test_assignment_is_stable_and_near_the_share():
    exp = uuid.uuid4()
    arms = [assign_arm(exp, f"visitor-{i:06d}", 10) for i in range(20_000)]
    share = arms.count("holdout") / len(arms)
    assert 0.09 < share < 0.11
    assert assign_arm(exp, "visitor-000042", 10) == arms[42]
    # A new run reshuffles visitors.
    other = [assign_arm(uuid.uuid4(), f"visitor-{i:06d}", 10) for i in range(2000)]
    assert other != arms[:2000]


def test_goal_path_validation():
    assert clean_goal_path(" /thank-you/ ") == "/thank-you"
    assert clean_goal_path("") is None and clean_goal_path(None) is None
    for bad in ("thank-you", "/a?b=1", "https://x.example/thanks"):
        with pytest.raises(ValueError):
            clean_goal_path(bad)


# ---- the flow, end to end -------------------------------------------------------

def _tenant(client: TestClient) -> dict:
    email = f"exp_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register",
                      json={"email": email, "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _beacon(client: TestClient, path: str, body: dict, origin: str | None = None):
    """Post like navigator.sendBeacon: a JSON string sent as text/plain."""
    import json
    headers = {"Content-Type": "text/plain"}
    if origin:
        headers["Origin"] = origin
    return client.post(path, content=json.dumps(body), headers=headers)


def test_experiment_flow_measures_lift():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Lift Co"}, headers=h).json()
        wid, key = site["id"], site["public_key"]
        base = f"/tenant/websites/{wid}/experiment"

        assert client.get(base, headers=h).json()["enabled"] is False
        assert client.get(f"{base}/results", headers=h).json() is None
        # Before an experiment runs, enrolment is a no-op and the widget shows.
        off = _beacon(client, "/experiment/enroll", {"key": key, "visitor": "visitor-aaaa"}).json()
        assert off == {"experiment_id": None, "arm": None, "goal_path": None, "overrides": {},
                       "defaults": {"greeting": None, "design": "level1", "accent": ANY,
                                    "languages": ["en"],
                                    "widget_language": "auto", "greeting_hi": None,
                                    "starters": []}}

        bad = client.put(base, json={"enabled": True, "goal_path": "thanks"}, headers=h)
        assert bad.status_code == 422
        on = client.put(base, json={"enabled": True, "holdout_pct": 20, "goal_path": "/thanks/"},
                        headers=h).json()
        assert on["enabled"] and on["started_new_run"] and on["goal_path"] == "/thanks"
        exp_id = on["id"]

        arms: dict[str, str] = {}
        for i in range(400):
            v = f"visitor-{i:05d}"
            r = _beacon(client, "/experiment/enroll", {"key": key, "visitor": v}).json()
            assert r["experiment_id"] == exp_id and r["goal_path"] == "/thanks"
            arms[v] = r["arm"]
        holdouts = [v for v, a in arms.items() if a == "holdout"]
        agents = [v for v, a in arms.items() if a == "agent"]
        assert 50 < len(holdouts) < 110
        # Enrolling again never moves a visitor.
        again = _beacon(client, "/experiment/enroll", {"key": key, "visitor": holdouts[0]}).json()
        assert again["arm"] == "holdout"

        # Agent visitors convert at 50 %, holdout visitors at ~5 %.
        def convert(v, name="goal_page", exp=exp_id):
            return _beacon(client, "/experiment/convert", {
                "key": key, "visitor": v, "experiment_id": exp, "name": name}).json()["counted"]
        for i, v in enumerate(agents):
            if i % 2 == 0:
                assert convert(v)
        for i, v in enumerate(holdouts):
            if i % 20 == 0:
                assert convert(v)
        assert convert(agents[0], name="demo_booked")       # a second goal, same visitor
        assert not convert("visitor-never-enrolled")          # unknown visitor
        assert not convert(agents[1], exp=str(uuid.uuid4()))  # another run's id
        assert _beacon(client, "/experiment/convert", {
            "key": key, "visitor": agents[1], "experiment_id": "nope"}).status_code == 422
        assert _beacon(client, "/experiment/enroll", {"key": key, "visitor": "x"}).status_code == 422
        assert client.post("/experiment/enroll", content="not json",
                           headers={"Content-Type": "text/plain"}).status_code == 422

        res = client.get(f"{base}/results", headers=h).json()
        lift_ = res["lift"]
        assert lift_["agent"]["visitors"] == len(agents)
        assert lift_["holdout"]["visitors"] == len(holdouts)
        assert lift_["agent"]["converters"] == len(range(0, len(agents), 2))
        assert lift_["status"] == "significant" and lift_["diff_low"] > 0 and lift_["seq_low"] > 0

        # Bots are turned away and counted, never enrolled.
        bot = client.post("/experiment/enroll", content=f'{{"key": "{key}", "visitor": "visitor-bot-001"}}',
                          headers={"Content-Type": "text/plain", "User-Agent": "Googlebot/2.1"}).json()
        assert bot["arm"] is None
        auto = _beacon(client, "/experiment/enroll",
                       {"key": key, "visitor": "visitor-bot-002", "automated": True}).json()
        assert auto["arm"] is None
        assert client.get(base, headers=h).json()["bots_ignored"] == 2
        assert client.get(f"{base}/results", headers=h).json()["lift"]["agent"]["visitors"] == len(agents)

        # The planner: from the holdout's own rate, at this run's traffic.
        plan = client.get(f"{base}/plan", headers=h).json()
        assert plan["baseline_source"] == "observed"
        assert plan["baseline"] == pytest.approx(lift_["holdout"]["rate"])
        assert plan["visitors_so_far"] == 400 and plan["needed"]["total"] > 0
        assert plan["visitors_per_day"] == pytest.approx(400)   # under a day counts as one
        given = client.get(f"{base}/plan", params={"baseline": 0.03, "mde": 0.2, "holdout_pct": 50},
                           headers=h).json()
        assert given["baseline_source"] == "given" and given["holdout_pct"] == 50
        assert client.get(f"{base}/plan", params={"baseline": 2}, headers=h).status_code == 422
        assert res["series"][-1]["agent_visitors"] == len(agents)
        goals = {(g["name"], g["arm"]): g["events"] for g in res["goals"]}
        assert goals[("demo_booked", "agent")] == 1

        # A new holdout share is a new run: fresh numbers.
        moved = client.put(base, json={"enabled": True, "holdout_pct": 30, "goal_path": "/thanks"},
                           headers=h).json()
        assert moved["started_new_run"] and moved["id"] != exp_id
        assert client.get(f"{base}/results", headers=h).json()["lift"]["agent"]["visitors"] == 0
        # Changing only the goal keeps the run.
        kept = client.put(base, json={"enabled": True, "holdout_pct": 30, "goal_path": "/booked"},
                          headers=h).json()
        assert not kept["started_new_run"] and kept["id"] == moved["id"]
        restarted = client.post(f"{base}/restart", headers=h).json()
        assert restarted["id"] != moved["id"] and restarted["holdout_pct"] == 30

        # Stopping it: no new enrolments, and the old run's results stay readable.
        stopped = client.put(base, json={"enabled": False, "holdout_pct": 30}, headers=h).json()
        assert stopped["status"] == "stopped"
        assert _beacon(client, "/experiment/enroll",
                       {"key": key, "visitor": "visitor-late-01"}).json()["arm"] is None
        assert client.get(f"{base}/results", headers=h).json()["experiment"]["status"] == "stopped"

        # Other tenants can't see or change it; demo sites never run one.
        h2 = _tenant(client)
        assert client.get(base, headers=h2).status_code == 404
        assert client.put(base, json={"enabled": True}, headers=h2).status_code == 404
        demo = _beacon(client, "/experiment/enroll", {"site": "hirebuddha", "visitor": "visitor-demo-1"})
        assert demo.json()["arm"] is None


def test_enrolment_respects_the_site_domain():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Dom Co", "domain": "dom.example"},
                           headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/experiment", json={"enabled": True}, headers=h)
        from app.config import get_settings
        get_settings().app_env = "production"  # dev skips the domain check; restored by conftest
        body = {"key": site["public_key"], "visitor": "visitor-origin-1"}
        assert _beacon(client, "/experiment/enroll", body, origin="https://evil.example").status_code == 403
        ok = _beacon(client, "/experiment/enroll", body, origin="https://www.dom.example")
        assert ok.status_code == 200 and ok.json()["arm"] in ("agent", "holdout")
