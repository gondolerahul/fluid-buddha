"""Generative experience Phase 4 (free-form pages, G3): fragments, assembly, the model
composer, budget, governance (blocked routes, pinned regions, review feed), flows and
half-width regions, the free-form test arm, and per-fragment rewards."""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.apis.registry import SiteApiRegistry
from app.experience import freeform as ff
from app.experience.intent import Intent, Signals
from app.experience.manifest import default_manifest
from app.experience.plan import validate_plan
from app.experience.routes_store import Route
from app.experience.ssr import render_fragment

KNOWLEDGE = """[Page: /]

Orbit is clinic scheduling software that fills every appointment slot automatically.
Patients book online at any hour, and reminders by SMS and WhatsApp cut no-shows across the practice.
Hospital IT teams get single sign-on with Azure AD and a full audit log of every change.
Every plan includes online booking, reminders and a shared calendar for doctors.
"""


def run(c):
    return asyncio.run(c)


# ---- unit ----------------------------------------------------------------------------

def test_blocked_routes_and_fingerprints():
    assert ff.blocked_route("/checkout", ff.DEFAULT_BLOCKED) == "/checkout*"
    assert ff.blocked_route("/legal/:doc", ff.DEFAULT_BLOCKED) == "/legal*"
    assert ff.blocked_route("/pricing", ff.DEFAULT_BLOCKED) is None
    a = {"id": "hero", "component": "fb.hero", "props": {"title": "x", "subtitle": "y"}}
    b = {"id": "other", "component": "fb.hero", "props": {"subtitle": "y", "title": "x"}}
    assert ff.fingerprint(a) == ff.fingerprint(b)  # same content, any id or key order


def test_score_and_assemble():
    def frag(fid, purpose, family="general", lang="en", hits=0, rewards=0, status="auto", taste=""):
        return {"id": fid, "purpose": purpose, "component": "fb.text", "status": status, "hit_count": hits,
                "rewards": rewards, "region": {"component": "fb.text", "props": {"body": purpose}},
                "conditions": {"family": family, "lang": lang, "taste": taste}}
    intent = Intent("compare-plans", "Comparing plans")
    assert ff.score(frag("1", "hero", family="other-goal"), intent, "", "en") == -1
    assert ff.score(frag("1", "hero", lang="hi"), intent, "", "en") == -1
    assert ff.score(frag("1", "hero", family="compare-plans"), intent, "", "en") > ff.score(frag("2", "hero"), intent, "", "en")
    assert ff.score(frag("1", "hero", status="pinned"), intent, "", "en") >= 10
    assert ff.score(frag("1", "hero", hits=100, rewards=40), intent, "", "en") > ff.score(frag("2", "hero", hits=100), intent, "", "en")
    regions, used = ff.assemble([frag("a", "next"), frag("b", "hero"), frag("c", "faq"), frag("d", "hero"),
                                 frag("e", "custom")])
    assert [r["id"] for r in regions] == ["hero", "faq", "next", "custom"] and used == ["b", "c", "a", "e"]


def test_pinned_flags_flow_and_width():
    pinned = [{"id": "notice", "component": "fb.text", "props": {"body": "Prices exclude GST."}, "position": "bottom"},
              {"id": "brand", "component": "fb.hero", "props": {"title": "Orbit"}, "position": "top"}]
    regions = [{"id": "brand", "component": "fb.text", "props": {"body": "x"}},
               {"id": "intro", "component": "fb.text", "props": {"body": "y"}}]
    out = ff.apply_pinned(regions, pinned)
    assert [r["id"] for r in out] == ["brand", "intro", "notice"] and out[0]["component"] == "fb.hero"
    assert "position" not in out[0]
    m = default_manifest()
    rep = validate_plan({"layout": "split", "regions": [
        {"id": "a", "component": "fb.text", "props": {"body": "x"}, "width": "half"},
        {"id": "b", "component": "fb.text", "props": {"body": "y"}, "width": "weird"},
        {"id": "c", "component": "fb.cta", "props": {"title": "Go", "cta_label": "Book"}}],
        "flow": [{"step": "Compare", "title": "Compare", "regions": ["a", "ghost"]},
                 {"step": "book", "regions": ["c"]}, {"step": "empty", "regions": ["ghost"]}]},
        manifest=m, catalogue=SiteApiRegistry("s", {}))
    assert [r.width for r in rep.plan.regions] == ["half", "full", "full"] and rep.plan.layout == "split"
    assert rep.plan.flow == [{"step": "compare", "title": "Compare", "regions": ["a"]},
                             {"step": "book", "title": "book", "regions": ["c"]}]
    assert rep.plan.to_dict()["regions"][0]["width"] == "half" and "width" not in rep.plan.to_dict()["regions"][1]
    one = validate_plan({"regions": [{"id": "a", "component": "fb.text", "props": {"body": "x"}}],
                         "flow": [{"step": "only", "regions": ["a"]}]}, manifest=m, catalogue=SiteApiRegistry("s", {}))
    assert one.plan.flow == []  # a single step is no flow
    flags = ff.flags_for(one, m, [{"id": "notice"}], ["bad-region"])
    assert set(flags) == {"validator", "few regions", "no call to action", "pinned region missing"}


def test_ssr_steps_and_halves():
    html = render_fragment([{"type": "text", "id": "a", "component": "fb.text", "props": {"body": "x"}, "width": "half"},
                            {"type": "cta", "id": "c", "component": "fb.cta", "props": {"title": "Go", "cta_label": "Book"}}],
                           plan_id="pl_0123456789", title="T",
                           flow=[{"step": "compare", "title": "Compare", "regions": ["a"]},
                                 {"step": "book", "title": "Book", "regions": ["c"]}])
    assert 'data-fb-step="compare"' in html and 'data-fb-step="book"' in html and 'data-fb-width="half"' in html
    assert '<ol class="fb-steps"><li data-fb-step-nav="compare">Compare</li>' in html


def test_compose_reuses_fragments_and_writes_new_regions():
    from app.ai.base import LLMResponse, ToolCall

    class LLM:
        prompt = ""

        async def generate(self, **kw):
            LLM.prompt = kw["messages"][0].text
            return LLMResponse(tool_calls=[ToolCall("compose_page", {"title": "For you", "layout": "split", "regions": [
                {"use": "F1"},
                {"id": "why", "component": "fb.text", "props": {"body": "Book online at any hour."}, "width": "half"},
                {"id": "next", "component": "fb.cta", "props": {"title": "Book a demo", "cta_label": "Book"}}],
                "flow": [{"step": "learn", "regions": ["hero", "why"]}, {"step": "book", "regions": ["next"]}]})])

    class Bridge:
        async def search(self, q, top_k=6):
            return [{"content": "Patients book online at any hour, and reminders cut no-shows.", "score": 0.9,
                     "document_title": "Home"}]

    class DB:
        async def execute(self, *a, **k):
            class R:
                def all(self_inner):
                    return []
            return R()

    class RT:
        class settings:
            cortex_confidence_threshold = 0.3

        def bridge(self, db, site_key):
            return Bridge()

    frags = [{"id": "f-1", "purpose": "hero", "component": "fb.hero", "status": "auto", "hit_count": 0, "rewards": 0,
              "region": {"id": "hero", "component": "fb.hero", "props": {"title": "Fill every slot"}}, "conditions": {}}]
    got = run(ff.compose(DB(), RT(), "s", Route("r", "/", "Home", "Introduce"), {}, Intent(), Signals(page="/"),
                         manifest=default_manifest(), registry=SiteApiRegistry("s", {}), llm=LLM(), model=None,
                         frags=frags))
    assert "[F1] purpose hero, fb.hero" in LLM.prompt
    assert [r["id"] for r in got["plan_raw"]["regions"]] == ["hero", "why", "next"]
    assert got["used"] == ["f-1"] and [r["id"] for r in got["new_regions"]] == ["why", "next"]
    assert got["plan_raw"]["regions"][1]["width"] == "half" and len(got["plan_raw"]["flow"]) == 2


# ---- API -----------------------------------------------------------------------------------

def _site(client):
    body = client.post("/auth/register", json={"email": f"ff_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": "supersecret1"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Orbit"}, headers=h).json()
    w = f"/tenant/websites/{site['id']}"
    assert client.post(f"{w}/sources", headers=h, json={"kind": "text", "name": "Orbit",
                                                        "content": KNOWLEDGE}).status_code == 201
    assert client.post(f"{w}/ingestion/run?wait=true", headers=h).json()["status"] == "done"
    return h, site, w


def _page(client, site, visitor=None, **extra):
    q = f"/experience/page?key={site['public_key']}&path=/" + (f"&visitor={visitor}" if visitor else "")
    return client.get(q, **extra).json()


def test_route_governance_and_settings():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        s = client.get(f"{w}/freeform", headers=h).json()
        assert s["freeform_enabled"] and "/checkout*" in s["g3_blocked_patterns"]
        bad = client.post(f"{w}/routes", headers=h, json={"pattern": "/checkout", "mode": "freeform"})
        assert bad.status_code == 422 and "never be free-form" in bad.text
        bad_pin = client.post(f"{w}/routes", headers=h, json={"pattern": "/", "mode": "freeform",
                                                              "pinned_regions": [{"id": "x", "component": "fb.nope"}]})
        assert bad_pin.status_code == 422
        ok = client.post(f"{w}/routes", headers=h, json={"pattern": "/", "title": "Home", "mode": "freeform",
                                                         "pinned_regions": [{"id": "notice", "component": "fb.text",
                                                                             "props": {"body": "Prices exclude GST."},
                                                                             "position": "bottom"}]}).json()
        assert ok["mode"] == "freeform" and ok["pinned_regions"][0]["position"] == "bottom"
        upd = client.put(f"{w}/freeform", headers=h, json={"g3_daily_budget": 5, "review_sample_pct": 100,
                                                           "g3_blocked_patterns": ["/checkout*", "/admin*"]}).json()
        assert upd["g3_daily_budget"] == 5 and upd["g3_blocked_patterns"] == ["/checkout*", "/admin*"]
        assert client.put(f"{w}/freeform", headers=h, json={"g3_blocked_patterns": ["no-slash"]}).status_code == 422


def test_serving_assembles_stays_stable_and_reviews():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        client.put(f"{w}/freeform", headers=h, json={"review_sample_pct": 100})
        client.post(f"{w}/routes", headers=h, json={
            "pattern": "/", "title": "Home", "mode": "freeform",
            "pinned_regions": [{"id": "notice", "component": "fb.text", "props": {"body": "Prices exclude GST."},
                                "position": "bottom"}]})
        v = "visitor-ff-0001"
        first = _page(client, site, v)
        assert first["status"] == 200 and not first.get("freeform")  # nothing to assemble yet: the G2 page
        frags = client.get(f"{w}/fragments", headers=h).json()["fragments"]
        assert len(frags) >= 3 and {"hero", "intro", "next"} <= {f["purpose"] for f in frags}  # seeded from G2

        second = _page(client, site, v)
        assert second["freeform"] and second["served"] == "assembled"
        assert 'data-fb-region="notice"' in second["html"] and second["html"].rindex("notice") > second["html"].index("hero")
        third = _page(client, site, v)
        assert third["served"] == "stable" and third["plan_id"] == second["plan_id"]  # the visitor's page stays put
        assert third["head"]["robots"].startswith("noindex")
        other = _page(client, site, "visitor-ff-0002")
        assert other["freeform"] and other["plan_id"] != second["plan_id"]  # per person
        assert not _page(client, site).get("freeform")  # no visitor id: the G2 page
        assert not _page(client, site, v, headers={"user-agent": "Googlebot/2.1"}).get("freeform")  # crawlers: never G3

        # Rewards credit the fragments the page was assembled from.
        assert client.post("/experience/feedback", json={"key": site["public_key"], "visitor": v,
                                                         "plan_id": second["plan_id"], "event": "engage"}).json()["counted"] == 1
        rewarded = [f for f in client.get(f"{w}/fragments", headers=h).json()["fragments"] if f["rewards"] > 0]
        assert rewarded

        # Review feed: sampled at 100 %; flagging blocks the page and its fragments.
        reviews = client.get(f"{w}/reviews", headers=h).json()["reviews"]
        assert reviews and "<section data-region=" in reviews[0]["preview_html"]
        target = next(r for r in reviews if r["plan"]["plan_id"] == second["plan_id"])
        assert client.put(f"{w}/reviews/{target['id']}", headers=h, json={"verdict": "flagged"}).json()["status"] == "flagged"
        blocked = {f["id"] for f in client.get(f"{w}/fragments?status_filter=blocked", headers=h).json()["fragments"]}
        assert set(target["plan"]["provenance"]["fragments"]) <= blocked
        again = _page(client, site, v)
        assert again["plan_id"] != second["plan_id"]  # the flagged page is never served again

        # Pin / block fragments by hand; off switch.
        fid = client.get(f"{w}/fragments", headers=h).json()["fragments"][0]["id"]
        assert client.put(f"{w}/fragments/{fid}", headers=h, json={"status": "pinned"}).json()["status"] == "pinned"
        client.put(f"{w}/freeform", headers=h, json={"freeform_enabled": False})
        assert not _page(client, site, "visitor-ff-0003").get("freeform")


def test_freeform_test_arm_and_budget():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client)
        client.post(f"{w}/routes", headers=h, json={"pattern": "/", "title": "Home", "mode": "freeform"})
        _page(client, site, "visitor-seed-001")  # seeds fragments from the G2 page
        t = client.post(f"{w}/tests", headers=h, json={
            "name": "G3 vs G2", "subject": "freeform", "holdout_pct": 0,
            "variants": [{"label": "Composed", "overrides": {"freeform": False}},
                         {"label": "Free-form", "overrides": {"freeform": True}}]})
        assert t.status_code in (200, 201), t.text
        seen = set()
        for i in range(24):
            seen.add(bool(_page(client, site, f"visitor-arm-{i:04d}").get("freeform")))
        assert seen == {True, False}
        assert client.post(f"{w}/tests/{t.json()['id']}/promote", headers=h, json={"variant": "a"}).status_code == 200
        assert client.get(f"{w}/freeform", headers=h).json()["freeform_enabled"] is False

        # Budget: spending counts per day and visitor.
        from app.db import session_scope

        async def budget():
            async with session_scope() as db:
                cfg = {"g3_daily_budget": 2, "g3_visitor_budget": 1}
                assert await ff.budget_left(db, site["site_key"], "visitor-b-0001", cfg)
                await ff.spend(db, site["site_key"], "visitor-b-0001")
                assert not await ff.budget_left(db, site["site_key"], "visitor-b-0001", cfg)  # visitor's own budget
                assert await ff.budget_left(db, site["site_key"], "visitor-b-0002", cfg)
                await ff.spend(db, site["site_key"], "visitor-b-0002")
                assert not await ff.budget_left(db, site["site_key"], "visitor-b-0003", cfg)  # the site's daily budget
        client.portal.call(budget)


def test_route_switched_to_freeform_seeds_from_its_pages():
    """A route that already had composed pages (built before free-form, so no
    fragments) assembles a visitor's page from those pages at once."""
    from app.main import app
    from sqlalchemy import text

    from app.db import session_scope

    with TestClient(app) as client:
        h, site, w = _site(client)
        r = client.post(f"{w}/routes", headers=h, json={"pattern": "/", "title": "Home"}).json()
        assert _page(client, site)["status"] == 200  # a composed page

        async def wipe():
            async with session_scope() as db:
                await db.execute(text("DELETE FROM fragment_cache WHERE site_key = :sk"), {"sk": site["site_key"]})
                await db.commit()
        client.portal.call(wipe)
        assert client.get(f"{w}/fragments", headers=h).json()["fragments"] == []
        client.put(f"{w}/routes/{r['id']}", headers=h, json={"pattern": "/", "title": "Home", "mode": "freeform"})
        got = _page(client, site, "visitor-switch-01")
        assert got["freeform"] and got["served"] == "assembled"
        assert client.get(f"{w}/fragments", headers=h).json()["fragments"]
        # The hosted shell reads the visitor from the widget's cookie on its own origin.
        hosted = client.get(f"/g/{site['site_key']}/", cookies={"fbvid": "visitor-switch-01"})
        assert hosted.status_code == 200 and got["plan_id"] in hosted.text
