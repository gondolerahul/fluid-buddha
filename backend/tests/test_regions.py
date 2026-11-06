"""Generative experience Phase 1 (adaptive regions, G1): intent resolver, region
planner, plan cache, the public regions endpoint, the console, and region tests."""
from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.experience import intent as intent_mod
from app.experience.intent import Intent, Signals, resolve_intent, rule_match, suggest_families
from app.experience.manifest import default_manifest
from app.experience.planner import Material, compose_rules, enforce
from app.experience.regions_store import IntentFamily, RegionSlot, clean_rules, normalize_page, plan_cache_key

KNOWLEDGE = """[Page: /pricing]

Orbit plans start with Starter for small clinics and grow to Enterprise for hospital groups.
Every plan includes online booking, reminders by SMS and WhatsApp, and a shared calendar for doctors.
Annual billing saves two months compared with paying monthly for the same plan.

[Page: /]

Orbit is clinic scheduling software that fills every appointment slot automatically.
Patients book online at any hour, and reminders cut no-shows across the whole practice.
Hospital IT teams get single sign-on with Azure AD and a full audit log of every change.
"""


def fam(slug, label, rules=None, priority=0, description="", stage=""):
    return IntentFamily(id=slug, slug=slug, label=label, description=description, stage=stage,
                        rules=clean_rules(rules or {}), priority=priority, updated_at="1")


# ---- P1-2: intent resolver ---------------------------------------------------

def test_signals_text_and_fingerprint():
    s = Signals.from_dict({"utm_campaign": "Switch-From-RivalCo", "referrer": "https://www.google.com/search?q=orbit+vs+rival",
                           "q": ""}, page="/Pricing/?x=1")
    assert s.page == "/pricing" and s.referrer_host == "www.google.com"
    assert "pricing" in s.text() and "switch from rivalco" in s.text() and "orbit vs rival" in s.text()
    assert s.fingerprint("a") == Signals.from_dict({"utm_campaign": "switch-from-rivalco",
                                                   "referrer": "https://www.google.com/search?q=orbit+vs+rival"},
                                                  page="/pricing").fingerprint("a")
    assert normalize_page("pricing/") == "/pricing" and normalize_page("") == "/"


def test_rules_win_by_priority():
    fams = [fam("compare-plans", "Comparing plans", {"paths": ["/pricing*"]}, priority=1),
            fam("switchers", "Switching", {"utm_campaign": ["switch-*"], "query_terms": ["vs"]}, priority=5),
            fam("general", "General")]
    s = Signals.from_dict({"utm_campaign": "switch-from-rivalco"}, page="/pricing")
    got = asyncio.run(resolve_intent("site", fams, s))
    assert (got.family, got.source, got.confidence) == ("switchers", "rule", 0.9)
    assert rule_match(fams[0], s) == ["path /pricing*"]
    q = Signals.from_dict({"q": "orbit vs calendly"}, page="/blog/x")
    assert asyncio.run(resolve_intent("site", fams, q)).family == "switchers"
    none = asyncio.run(resolve_intent("site", fams, Signals.from_dict({}, page="/about")))
    assert none.family == "general" and none.source == "default"


def test_embedding_step_and_threshold():
    intent_mod.clear_intent_caches()
    vectors = {"security": [1.0, 0.0], "pricing": [0.0, 1.0]}

    async def embed(text):
        t = text.lower()
        if "security" in t or "sso" in t:
            return vectors["security"]
        if "plan" in t or "pricing" in t:
            return vectors["pricing"]
        return [0.7, 0.7]

    fams = [fam("security-review", "Security review", description="SSO, compliance"),
            fam("compare-plans", "Comparing plans", description="pricing and plans")]
    got = asyncio.run(resolve_intent("s", fams, Signals.from_dict({"q": "does it support sso"}, page="/blog"),
                                     embed=embed))
    assert got.family == "security-review" and got.source == "embedding" and got.confidence > 0.9
    # Ambiguous text (cosine ~0.707 to both) clears the 0.6 bar, picks one deterministically;
    # an orthogonal vector does not.
    async def flat(text):
        return [0.0, 0.0, 1.0] if "zzz" in text else vectors["pricing"] + [0.0]
    fams3 = [fam("a-fam", "Alpha", description="pricing"), fam("b-fam", "Beta", description="pricing")]
    low = asyncio.run(resolve_intent("s2", fams3, Signals.from_dict({"q": "zzz"}, page="/x"), embed=flat))
    assert low.family == "general"


def test_background_classification_is_remembered():
    intent_mod.clear_intent_caches()
    calls = []

    async def classify(families, sig):
        calls.append(sig.page)
        return "compare-plans"

    fams = [fam("compare-plans", "Comparing plans")]
    sig = Signals.from_dict({"q": "how much"}, page="/blog/costs")

    async def run():
        first = await resolve_intent("s", fams, sig, classify=classify)
        await asyncio.sleep(0.01)  # the background task runs
        second = await resolve_intent("s", fams, sig, classify=classify)
        return first, second

    first, second = asyncio.run(run())
    assert first.family == "general" and second.family == "compare-plans" and second.source == "model"
    assert calls == ["/blog/costs"]


def test_suggest_families_from_routes():
    got = {s["slug"]: s for s in suggest_families(["/pricing", "/integrations/slack", "/about", "/book-a-demo"],
                                                  [("clinic-owner", "Clinic owners")])}
    assert got["compare-plans"]["rules"]["paths"] == ["/pricing*"]
    assert "/integrations/slack*" in got["integration-check"]["rules"]["paths"]
    assert "ready-to-talk" in got and "for-clinic-owner" in got and "general" in got


def test_clean_rules():
    assert clean_rules({"paths": "/a*, /b", "utm_source": ["Google", " "], "evil": ["x"]}) == {
        "paths": ["/a*", "/b"], "utm_source": ["google"]}


# ---- P1-3: planner -----------------------------------------------------------

def _material():
    return Material(sources={
        "S1": {"text": "Every plan includes online booking, reminders by SMS and WhatsApp, and a shared calendar. "
                       "Annual billing saves two months compared with paying monthly.", "label": "Pricing"},
        "S2": {"text": "Patients book online at any hour, and reminders cut no-shows across the practice.",
               "label": "Home"}},
        golden=[("Is there a free trial?", "Yes, 14 days on every plan."), ("Do you support SSO?", "Yes, Azure AD.")])


def test_compose_rules_fills_supported_slots_only():
    slots = [RegionSlot(id="1", name="hero", label="Welcome", components=["fb.hero"]),
             RegionSlot(id="2", name="proof", components=["fb.feature_grid"]),
             RegionSlot(id="3", name="questions", components=["fb.faq"]),
             RegionSlot(id="4", name="chart", components=["fb.chart"])]
    intent = Intent("compare-plans", "Comparing plans", "evaluate", 0.9, "rule")
    regions = compose_rules(slots, default_manifest(), intent, Signals(page="/pricing"), _material())
    by = {r["id"]: r for r in regions}
    assert set(by) == {"hero", "proof", "questions"}  # no material can fill a chart
    assert by["hero"]["props"]["title"] == "Comparing plans"
    assert by["hero"]["props"]["subtitle"] in _material().all_text()
    assert len(by["proof"]["props"]["items"]) == 2
    assert by["questions"]["props"]["items"][0]["q"]


def test_enforce_slots_components_and_numbers():
    slots = [RegionSlot(id="1", name="hero", components=["fb.hero"])]
    raw = [{"id": "hero", "component": "fb.hero",
            "props": {"title": "Save two months", "subtitle": "Trusted by 10,000 clinics"}},
           {"id": "hero", "component": "fb.hero", "props": {"title": "dup"}},
           {"id": "sidebar", "component": "fb.hero", "props": {"title": "x"}},
           ]
    out, dropped = enforce(raw, slots, default_manifest(), _material())
    assert out == [{"id": "hero", "component": "fb.hero", "props": {"title": "Save two months"}}]
    assert any("10,000" in d or "number" in d for d in dropped)
    bad, dropped = enforce([{"id": "hero", "component": "fb.text", "props": {"body": "x"}}], slots,
                           default_manifest(), _material())
    assert bad == [] and "not allowed" in dropped[0]


def test_build_plan_with_a_fake_model():
    from app.ai.base import LLMResponse, ToolCall
    from app.apis.registry import SiteApiRegistry
    from app.experience.planner import build_plan

    class FakeLLM:
        async def generate(self, **kw):
            assert "SLOTS:" in kw["messages"][0].text and "compose_regions" == kw["tools"][0].name
            return LLMResponse(tool_calls=[ToolCall("compose_regions", {"regions": [
                {"region": "hero", "component": "fb.hero",
                 "props": {"title": "Plans that save two months", "subtitle": "Book online at any hour."},
                 "sources": ["S1"]}]})], input_tokens=10, output_tokens=5)

    class FakeBridge:
        async def search(self, q, top_k=6):
            return [{"content": _material().sources["S1"]["text"], "score": 0.9, "document_title": "Pricing"}]

    class FakeDB:
        async def execute(self, *a, **k):
            class R:
                def all(self_inner):
                    return []
            return R()

    class RT:
        class settings:
            cortex_confidence_threshold = 0.3

        def bridge(self, db, site_key):
            return FakeBridge()

    slots = [RegionSlot(id="1", name="hero", components=["fb.hero"])]
    out = asyncio.run(build_plan(FakeDB(), RT(), "s", slots, Intent("x", "X"), Signals(page="/"),
                                 manifest=default_manifest(), registry=SiteApiRegistry("s", {}), llm=FakeLLM()))
    assert out["composer"] == "model" and out["tokens"] == [10, 5]
    assert out["plan"]["regions"][0]["id"] == "hero"
    assert out["plan"]["provenance"]["composer"] == "model"


def test_cache_key_is_order_insensitive():
    a = plan_cache_key(family="f", persona="", lang="en", page="/x/", regions=["b", "a"], content_version="1",
                       manifest_version=None)
    b = plan_cache_key(family="f", persona="", lang="en", page="/x", regions=["a", "b"], content_version="1",
                       manifest_version=None)
    assert a == b and a != plan_cache_key(family="f", persona="", lang="en", page="/x", regions=["a", "b"],
                                          content_version="2", manifest_version=None)


# ---- console + public endpoint ----------------------------------------------

def _site(client):
    body = client.post("/auth/register", json={"email": f"rg_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": "supersecret1"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Orbit"}, headers=h).json()
    w = f"/tenant/websites/{site['id']}"
    assert client.post(f"{w}/sources", headers=h, json={"kind": "text", "name": "Orbit",
                                                        "content": KNOWLEDGE}).status_code == 201
    assert client.post(f"{w}/ingestion/run?wait=true", headers=h).json()["status"] == "done"
    return h, site, w


def _regions(client, site, **body):
    return client.post("/experience/regions", json={"key": site["public_key"], "page": "/pricing",
                                                    "regions": ["hero", "proof"], **body})


def test_console_slots_families_and_plans():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        assert client.get(f"{w}/regions/settings", headers=h).json()["regions_enabled"] is True
        bad = client.put(f"{w}/regions/Hero!", headers=h, json={})
        assert bad.status_code == 422
        assert client.put(f"{w}/regions/hero", headers=h, json={"components": ["fb.nope"]}).status_code == 422
        assert client.put(f"{w}/regions/hero", headers=h, json={
            "label": "Welcome", "components": ["fb.hero", "fb.text"], "pages": ["/pricing*"]}).status_code == 200
        assert client.put(f"{w}/regions/proof", headers=h, json={
            "components": ["fb.feature_grid", "fb.text"]}).status_code == 200
        assert client.put(f"{w}/regions/x", headers=h, json={"pages": ["no-slash"]}).status_code == 422
        regions = client.get(f"{w}/regions", headers=h).json()
        assert [r["name"] for r in regions["regions"]] == ["hero", "proof"]
        assert any(c["id"] == "fb.hero" for c in regions["components"])

        assert client.put(f"{w}/intent-families/compare-plans", headers=h, json={
            "label": "Comparing plans", "description": "Weighing up plans and prices", "stage": "evaluate",
            "rules": {"paths": ["/pricing*"]}, "priority": 2}).status_code == 200
        fams = client.get(f"{w}/intent-families", headers=h).json()["families"]
        assert fams[0]["rules"] == {"paths": ["/pricing*"]}
        tried = client.post(f"{w}/intent/resolve", headers=h, json={"page": "/pricing"}).json()
        assert tried["intent"]["family"] == "compare-plans" and tried["intent"]["source"] == "rule"
        assert isinstance(client.get(f"{w}/intent-families/suggest", headers=h).json()["suggestions"], list)

        gen = client.post(f"{w}/plans/generate", headers=h, json={"page": "/pricing"})
        assert gen.status_code == 201, gen.text
        plan = gen.json()
        assert plan["family"] == "compare-plans" and plan["composer"] == "rules"
        assert "hero" in plan["rendered"], plan
        assert "<section data-region='hero'>" in plan["preview_html"] and "<script" not in plan["preview_html"]
        listed = client.get(f"{w}/plans?family=compare-plans", headers=h).json()["plans"]
        assert len(listed) == 1 and "plan" not in listed[0]

        # The public endpoint now serves it from the cache.
        got = _regions(client, site, visitor="visitor-0001").json()
        assert got["cache"] == "hit" and "hero" in got["regions"] and got["intent"]["family"] == "compare-plans"
        assert got["regions"]["hero"]["id"] == "hero" and got["tokens"]["--ds-color-primary"]

        # Pin and block.
        pid = listed[0]["id"]
        assert client.put(f"{w}/plans/{pid}", headers=h, json={"status": "pinned"}).json()["status"] == "pinned"
        assert _regions(client, site).json()["cache"] == "pinned"
        blocked = client.put(f"{w}/plans/{pid}", headers=h, json={"status": "blocked"}).json()
        assert blocked["status"] == "blocked" and "#blocked#" in blocked["cache_key"]
        miss = _regions(client, site).json()
        assert miss["pending"] and miss["cache"] == "miss" and miss["regions"] == {}

        # Off switch.
        client.put(f"{w}/regions/settings", headers=h, json={"regions_enabled": False})
        assert _regions(client, site).json()["reason"] == "off"
        client.put(f"{w}/regions/settings", headers=h, json={"regions_enabled": True})

        assert client.delete(f"{w}/plans/{pid}", headers=h).status_code == 204
        assert client.delete(f"{w}/regions/proof", headers=h).status_code == 204
        assert client.delete(f"{w}/intent-families/compare-plans", headers=h).status_code == 204


def test_public_miss_builds_in_the_background_then_hits():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        client.put(f"{w}/regions/hero", headers=h, json={"components": ["fb.hero"]})
        first = _regions(client, site, regions=["hero", "nope"]).json()
        assert first["pending"] and first["retry_after_ms"] > 0
        got = None
        for _ in range(40):
            time.sleep(0.25)
            got = _regions(client, site, regions=["hero"]).json()
            if not got["pending"]:
                break
        assert got and got["cache"] == "hit" and "hero" in got["regions"]
        # Unknown slots, bots and other pages get nothing.
        assert _regions(client, site, regions=["nope"]).json()["reason"] == "no_slots"
        bot = client.post("/experience/regions", headers={"user-agent": "Googlebot/2.1"},
                          json={"key": site["public_key"], "page": "/", "regions": ["hero"]}).json()
        assert bot["reason"] == "bot"
        assert client.post("/experience/regions", json={"key": "fbk_nope", "regions": ["hero"]}).status_code == 403


def test_region_test_arms():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        client.put(f"{w}/regions/hero", headers=h, json={"components": ["fb.hero"]})
        client.post(f"{w}/plans/generate", headers=h, json={"page": "/pricing"})
        t = client.post(f"{w}/tests", headers=h, json={
            "name": "Generated hero", "subject": "regions", "holdout_pct": 0,
            "variants": [{"label": "Page's own", "overrides": {"regions": False}},
                         {"label": "Generated", "overrides": {"regions": True}}]})
        assert t.status_code in (200, 201), t.text
        arms = {}
        for i in range(30):
            v = f"visitor-{i:04d}x"
            r = _regions(client, site, visitor=v, regions=["hero"]).json()
            arms[r.get("arm")] = r
        assert set(arms) == {"a", "b"}
        assert arms["a"]["reason"] == "experiment_arm" and arms["a"]["regions"] == {}
        assert "hero" in arms["b"]["regions"]
        # Unidentified visitors are left out of a region test.
        assert _regions(client, site, regions=["hero"]).json()["reason"] == "experiment_arm"
        bad = client.post(f"{w}/tests", headers=h, json={
            "name": "x", "subject": "regions", "holdout_pct": 0,
            "variants": [{"overrides": {"regions": "yes"}}, {"overrides": {"regions": True}}]})
        assert bad.status_code == 422
        tid = t.json()["id"]
        promoted = client.post(f"{w}/tests/{tid}/promote", headers=h, json={"variant": "a"})
        assert promoted.status_code == 200
        assert client.get(f"{w}/regions/settings", headers=h).json()["regions_enabled"] is False
