"""Generative experience Phase 3 (personal experience): taste profiles, storage tied
to memory opt-in, tunables within brand limits, taste-aware plans, "why", bandits."""
from __future__ import annotations

import random
import time
import uuid

from fastapi.testclient import TestClient

from app.design.system import DesignSystem
from app.experience import taste as tm
from app.experience.bandit import choose_arm, outline, reward_rate, wants_new_arm
from app.experience.intent import Intent, Signals
from app.experience.personal import apply_tunables, explain
from app.experience.regions_store import plan_cache_key

KNOWLEDGE = """[Page: /pricing]

Orbit plans start with Starter for small clinics and grow to Enterprise for hospital groups.
Every plan includes online booking, reminders by SMS and WhatsApp, and a shared calendar for doctors.

[Page: /]

Orbit is clinic scheduling software that fills every appointment slot automatically.
Patients book online at any hour, and reminders cut no-shows across the whole practice.
"""


# ---- P3-1: model --------------------------------------------------------------

def test_explicit_beats_implicit_and_implicit_accumulates():
    t = tm.Taste()
    assert t.apply("format", "tables") and t.dims["format"]["confidence"] == 0.15
    for _ in range(4):
        t.apply("format", "tables")
    assert t.value("format") == "tables"  # ≥ 0.5 after repeated evidence
    t.apply("detail", "summary", explicit=True)
    assert not t.apply("detail", "deep")  # inference never overrides a choice
    assert t.value("detail") == "summary"
    assert not t.apply("format", "hologram") and not t.apply("religion", "x")  # only known dims/values
    # Contrary evidence weakens before it flips.
    conf = t.dims["format"]["confidence"]
    t.apply("format", "charts")
    assert t.dims["format"]["value"] == "tables" and t.dims["format"]["confidence"] < conf


def test_decay_and_bucket_and_brief():
    t = tm.Taste()
    t.dims["density"] = {"value": "compact", "confidence": 0.8, "source": "implicit", "at": time.time()}
    t.dims["format"] = {"value": "tables", "confidence": 0.8, "source": "implicit",
                        "at": time.time() - 60 * 24 * 3600}  # 60 days old: decayed below 0.5
    assert t.bucket() == "d:compact"
    t.apply("format", "charts", explicit=True)
    assert t.bucket() == "d:compact|f:visual"
    t.apply("detail", "summary", explicit=True)
    t.interest("pricing")
    assert "compact layouts" in t.brief() and "short summaries" in t.brief() and "pricing" in t.brief()
    assert tm.Taste().bucket() == "" and tm.Taste().brief() == ""


def test_from_text_and_events_and_clean():
    t = tm.Taste()
    assert tm.from_text(t, "Can you keep it short and show me a table?") == [("detail", "summary"), ("format", "tables")]
    assert t.dims["detail"]["source"] == "explicit"
    n = tm.apply_events(t, [{"type": "mic"}, {"type": "reduced_motion"}, {"type": "set", "dim": "tone", "value": "formal"},
                            {"type": "interest", "topic": "Security"}, {"type": "bogus"}, "junk",
                            {"type": "set", "dim": "tone", "value": "rude"}])
    assert n == 4 and t.dims["tone"]["value"] == "formal" and "security" in t.interests
    tm.apply_events(t, [{"type": "reset", "dim": "tone"}])
    assert "tone" not in t.dims
    dirty = {"dims": {"format": {"value": "tables", "confidence": 9, "source": "explicit", "at": time.time() + 999},
                      "evil": {"value": "x"}, "detail": {"value": "nope"}},
             "interests": {"ok topic": 3, "<script>": 1, "x": True}}
    c = tm.clean(dirty)
    assert set(c.dims) == {"format"} and c.dims["format"]["confidence"] == 1.0 and c.dims["format"]["at"] <= time.time()
    assert c.interests == {"ok topic": 3.0}
    assert tm.from_compact(tm.compact(t)).value("detail") == "summary"
    assert tm.from_compact("density:compact,evil:x,format:hologram").dims.keys() == {"density"}


def test_merge_prefers_explicit_then_newer():
    stored, session = tm.Taste(), tm.Taste()
    stored.apply("detail", "deep", explicit=True)
    session.apply("detail", "summary")  # implicit: doesn't beat a stored choice
    session.apply("format", "charts", explicit=True)
    m = stored.merge(session)
    assert m.dims["detail"]["value"] == "deep" and m.dims["format"]["value"] == "charts"


# ---- P3-3 / P3-5: tunables and why -------------------------------------------------

def test_tunables_only_within_brand_limits():
    design = DesignSystem.from_dict({
        "tunables": {"density": {"allowed": ["balanced", "compact"], "default": "balanced"},
                     "scheme": {"allowed": ["light", "dark"], "default": "light"},
                     "type_scale": {"allowed": ["large"], "default": "large"}},
        "schemes": {"dark": {"background": "#000000", "text": "#ffffff", "evil": "red;"}}})
    t = tm.Taste()
    t.apply("density", "airy", explicit=True)          # not allowed → the brand's default
    t.apply("motion", "calm", explicit=True)           # axis not tunable → untouched
    t.apply("scheme", "dark", explicit=True)
    tokens, applied = apply_tunables(design, t)
    assert applied == {"density": "balanced", "type_scale": "large", "scheme": "dark"}
    assert tokens["--ds-gap"] == "34px" and tokens["--ds-base-size"] == "18px"
    assert tokens["--ds-color-background"] == "#000000" and "--ds-color-evil" not in tokens
    assert "--ds-anim" not in tokens
    assert apply_tunables(DesignSystem.from_dict({}), t) == ({}, {})  # no tunables → nothing changes


def test_explain():
    t = tm.Taste()
    t.apply("detail", "summary", explicit=True)
    t.apply("density", "compact", explicit=True)
    why = explain(Intent("compare-plans", "Comparing plans", "evaluate", 0.9, "rule"),
                  Signals.from_dict({"utm_campaign": "spring"}, page="/pricing"), t, served="cached",
                  applied={"density": "compact"})
    assert why[0].startswith('You arrived from the "spring" campaign') and "comparing plans" in why[0]
    assert why[1] == "You asked for short summaries, a compact layout"
    assert explain(None, Signals(), None, served="pinned") == ["This is the version the site's team picked for this page"]
    assert explain(Intent(), Signals(), tm.Taste()) == []
    # The brand's default layout is never presented as the visitor's preference.
    assert explain(Intent(), Signals(), tm.Taste(), applied={"density": "airy"}) == []


# ---- P3-4: taste-aware planning ----------------------------------------------------

def test_cache_key_and_rules_follow_taste():
    from app.experience.manifest import default_manifest
    from app.experience.planner import Material, compose_rules
    from app.experience.regions_store import RegionSlot

    base = dict(family="f", persona="", lang="en", page="/x", regions=["a"], content_version="1", manifest_version=None)
    assert plan_cache_key(**base) == plan_cache_key(**base, taste="")  # pre-Phase-3 keys unchanged
    assert plan_cache_key(**base) != plan_cache_key(**base, taste="f:tables")
    m = Material(sources={"S1": {"text": "Every plan includes online booking and reminders. Annual billing saves two "
                                         "months compared with paying monthly. Patients book online at any hour. "
                                         "Reminders by SMS and WhatsApp cut no-shows. Hospital IT gets single sign-on "
                                         "with Azure AD. Every change is kept in a full audit log for admins.",
                                 "label": "Pricing"}})
    slot = [RegionSlot(id="1", name="intro", components=["fb.feature_grid", "fb.text"])]
    plain = compose_rules(slot, default_manifest(), Intent(), Signals(), m)
    prose = compose_rules(slot, default_manifest(), Intent(), Signals(), m, prefer="prose")
    assert plain[0]["component"] == "fb.feature_grid" and prose[0]["component"] == "fb.text"
    short = compose_rules([RegionSlot(id="1", name="intro", components=["fb.text"])], default_manifest(), Intent(),
                          Signals(), m, short=True)
    assert short[0]["props"]["body"].count(".") == 1
    alt = compose_rules(slot, default_manifest(), Intent(), Signals(), m, variant=1)
    assert alt[0]["component"] == "fb.text"  # a bandit arm takes the next fitting component


# ---- P3-6: bandits -------------------------------------------------------------------

def test_bandit_choice_and_new_arms():
    good = {"id": "g", "hit_count": 200, "rewards": 60, "plan": {"regions": [{"id": "hero", "component": "fb.hero"}]}}
    bad = {"id": "b", "hit_count": 200, "rewards": 5, "plan": {}}
    rng = random.Random(7)
    picks = [choose_arm([good, bad], explore_pct=0, rng=rng)["id"] for _ in range(200)]
    assert picks.count("g") > 190
    picks = [choose_arm([good, bad], explore_pct=50, rng=rng)["id"] for _ in range(400)]
    assert 60 < picks.count("b") < 160  # the exploration floor keeps traffic on every arm
    assert wants_new_arm([good], 2) and not wants_new_arm([good, bad], 2)
    assert not wants_new_arm([{"hit_count": 3}], 2)
    assert outline(good["plan"]) == ["hero:fb.hero"] and reward_rate(good) == 0.3 and reward_rate({"hit_count": 0}) is None


# ---- API ---------------------------------------------------------------------------------

def _site(client):
    body = client.post("/auth/register", json={"email": f"ps_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": "supersecret1"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Orbit"}, headers=h).json()
    w = f"/tenant/websites/{site['id']}"
    assert client.post(f"{w}/sources", headers=h, json={"kind": "text", "name": "Orbit",
                                                        "content": KNOWLEDGE}).status_code == 201
    assert client.post(f"{w}/ingestion/run?wait=true", headers=h).json()["status"] == "done"
    return h, site, w


def test_taste_endpoint_stores_only_for_remembered_visitors():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        key = site["public_key"]
        anon = client.post("/experience/taste", json={"key": key, "visitor": "visitor-anon-1",
                                                      "events": [{"type": "set", "dim": "detail", "value": "summary"}]})
        assert anon.status_code == 200 and anon.json()["stored"] is False
        assert anon.json()["dims"]["detail"] == {"value": "summary", "confidence": 1.0, "source": "explicit"}
        assert anon.json()["compact"] == "detail:summary" and "options" in anon.json()

        # The site offers memory and the visitor opts in → stored, and it follows forget.
        priv = client.get(f"{w}/privacy", headers=h).json()
        assert client.put(f"{w}/privacy", headers=h, json={**priv, "memory_enabled": True}).status_code == 200
        v = "visitor-mem-0001"
        assert client.post("/memory", json={"key": key, "visitor": v, "remember": True}).status_code == 200
        r = client.post("/experience/taste", json={"key": key, "visitor": v,
                                                   "events": [{"type": "set", "dim": "format", "value": "tables"}]}).json()
        assert r["stored"] is True
        again = client.post("/experience/taste", json={"key": key, "visitor": v, "events": []}).json()
        assert again["dims"]["format"]["value"] == "tables"  # loaded back from the server
        client.post("/memory", json={"key": key, "visitor": v, "remember": False})
        gone = client.post("/experience/taste", json={"key": key, "visitor": v, "events": []}).json()
        assert "format" not in gone["dims"] and gone["stored"] is False  # forget removed the profile


def test_regions_serve_tokens_why_and_taste_buckets():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        client.put(f"{w}/design-system", headers=h, json={
            "tunables": {"density": {"allowed": ["balanced", "compact"], "default": "balanced"}}})
        client.put(f"{w}/regions/hero", headers=h, json={"components": ["fb.hero"]})
        client.put(f"{w}/intent-families/compare-plans", headers=h, json={
            "label": "Comparing plans", "rules": {"paths": ["/pricing*"]}})
        compact = {"dims": {"density": {"value": "compact", "confidence": 1, "source": "explicit", "at": time.time()}}}
        body = {"key": site["public_key"], "page": "/pricing", "regions": ["hero"], "taste": compact}
        first = client.post("/experience/regions", json=body).json()
        assert first["pending"]
        got = None
        for _ in range(40):
            time.sleep(0.25)
            got = client.post("/experience/regions", json=body).json()
            if not got["pending"]:
                break
        assert "hero" in got["regions"] and got["tokens"]["--ds-gap"] == "18px"
        assert any("compact layout" in x for x in got["why"]) and any("comparing plans" in x for x in got["why"])
        # A visitor without that taste lands on a different cache key (pending again).
        plain = client.post("/experience/regions", json={**body, "taste": None}).json()
        assert plain["pending"]
        plans = client.get(f"{w}/plans", headers=h).json()["plans"]
        assert any(p["taste"] == "d:compact" for p in plans) and all("reward_rate" in p for p in plans)


def test_bandit_settings_feedback_and_arms():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        s = client.put(f"{w}/regions/settings", headers=h,
                       json={"regions_enabled": True, "bandit_enabled": True, "max_arms": 2, "explore_pct": 20}).json()
        assert s == {"regions_enabled": True, "bandit_enabled": True, "max_arms": 2, "explore_pct": 20}
        assert client.put(f"{w}/regions/settings", headers=h,
                          json={"regions_enabled": True, "max_arms": 9}).status_code == 422
        client.put(f"{w}/regions/hero", headers=h, json={"components": ["fb.hero", "fb.text"]})
        gen = client.post(f"{w}/plans/generate", headers=h, json={"page": "/pricing"}).json()
        pid = gen["plan"]["plan_id"]
        key = site["public_key"]
        fb = client.post("/experience/feedback", json={"key": key, "visitor": "visitor-fb-0001",
                                                       "plan_id": pid, "event": "engage"}).json()
        assert fb == {"counted": 1}
        dup = client.post("/experience/feedback", json={"key": key, "visitor": "visitor-fb-0001",
                                                        "plan_ids": [pid], "event": "engage"}).json()
        assert dup == {"counted": 0}  # once per visitor, plan and event
        assert client.post("/experience/feedback", json={"key": key, "visitor": "v", "plan_id": pid,
                                                         "event": "engage"}).status_code == 422
        bot = client.post("/experience/feedback", headers={"user-agent": "Googlebot/2.1"},
                          json={"key": key, "visitor": "visitor-bot-0001", "plan_id": pid, "event": "convert"}).json()
        assert bot == {"counted": 0}

        # Serve the plan until it has enough pulls: a second arm gets built in the background.
        from app.db import session_scope

        async def pulls():
            async with session_scope() as db:
                from sqlalchemy import text
                await db.execute(text("UPDATE plan_cache SET hit_count = 40 WHERE id = :id"), {"id": uuid.UUID(gen["id"])})
                await db.commit()
        client.portal.call(pulls)
        client.post("/experience/regions", json={"key": key, "page": "/pricing", "regions": ["hero"]})
        arms = []
        for _ in range(40):
            time.sleep(0.25)
            arms = [p for p in client.get(f"{w}/plans", headers=h).json()["plans"] if p["page"] == "/pricing"]
            if len(arms) >= 2:
                break
        assert sorted(p["arm"] for p in arms) == [0, 1]
        assert {p["base_key"] for p in arms} == {gen["cache_key"]}
        first = next(p for p in arms if p["arm"] == 0)
        assert first["rewards"] == 1 and first["reward_rate"] is not None


def test_design_system_schemes_validation():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        ok = client.put(f"{w}/design-system", headers=h, json={"schemes": {"dark": {"background": "#000000"}}})
        assert ok.status_code == 200 and ok.json()["effective"]["schemes"]["dark"]["background"] == "#000000"
        assert client.put(f"{w}/design-system", headers=h, json={"schemes": {"neon": {}}}).status_code == 422
        assert client.put(f"{w}/design-system", headers=h,
                          json={"schemes": {"dark": {"background": "black;x"}}}).status_code == 422
