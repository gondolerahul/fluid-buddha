"""Generative experience Phase 2 (composed pages, G2): route registry, entities and
connectors, entity/content bindings, SSR, the page planner, plan patches, and the
page endpoints."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.apis.registry import SiteApiRegistry
from app.experience import entities as ents
from app.experience.intent import Intent, Signals
from app.experience.manifest import default_manifest
from app.experience.patch import apply_ops, outline
from app.experience.plan import validate_plan
from app.experience.routes_store import Route, match_pattern, valid_pattern
from app.experience.ssr import page_data_json, render_document, render_section

KNOWLEDGE = """[Page: /pricing]

Orbit plans start with Starter for small clinics and grow to Enterprise for hospital groups.
Every plan includes online booking, reminders by SMS and WhatsApp, and a shared calendar for doctors.

[Page: /]

Orbit is clinic scheduling software that fills every appointment slot automatically.
Patients book online at any hour, and reminders cut no-shows across the whole practice.
"""


def run(c):
    return asyncio.run(c)


# ---- P2-5: route registry ----------------------------------------------------

def test_patterns_and_matching():
    assert valid_pattern("/") and valid_pattern("/products/:slug") and valid_pattern("/guides/*")
    assert not valid_pattern("/a b") and not valid_pattern("products") and not valid_pattern("/:Slug")
    assert match_pattern("/products/:slug", "/products/scale/") == {"slug": "scale"}
    assert match_pattern("/products/:slug", "/products") is None
    assert match_pattern("/guides/*", "/guides/setup/sso") == {"rest": "setup/sso"}
    assert match_pattern("/pricing", "/pricing") == {} and match_pattern("/pricing", "/pricing/x") is None
    exact, param, wild = Route("1", "/products/scale"), Route("2", "/products/:slug"), Route("3", "/products/*")
    assert exact.specificity > param.specificity > wild.specificity


# ---- P2-6: entities, import, connectors, bindings ---------------------------

def test_parse_import_json_and_csv():
    recs, probs = ents.parse_import(json.dumps({"items": [{"slug": "Scale Plan", "price": "₹9,999"},
                                                          {"name": "starter"}, {"x": 1}, "junk"]}), "json", "slug")
    assert [k for k, _ in recs] == ["scale-plan", "starter"] and len(probs) == 2
    recs, probs = ents.parse_import("slug,name,price\nscale,Scale,9999\nscale,Dup,1\n", "csv", "slug")
    assert recs == [("scale", {"slug": "scale", "name": "Scale", "price": "9999"})] and "duplicate" in probs[0]
    assert ents.check_record("product", "x", {}) and ents.check_record("Product", "x", []) and not \
        ents.check_record("Product", "x", {"a": 1})


def test_map_feed_json_and_wordpress():
    data = {"data": [{"attributes": {"slug": "a-1", "title": "A", "body": "x"}},
                     {"attributes": {"slug": "b-2", "title": "B"}}]}
    out = ents.map_feed(data, "json_feed", {"items_path": "$.data[*]", "key_field": "$.attributes.slug",
                                            "fields": {"title": "attributes.title", "body": "attributes.body"}})
    assert out == [("a-1", {"title": "A", "body": "x"}), ("b-2", {"title": "B"})]
    wp = [{"slug": "hello", "title": {"rendered": "Hello &amp; welcome"}, "excerpt": {"rendered": "<p>Short</p>"},
           "content": {"rendered": "<p>Long <b>body</b></p>"}, "link": "https://x.example/hello", "date": "2026-01-01",
           "_embedded": {"wp:featuredmedia": [{"source_url": "https://x.example/i.jpg"}]}}]
    (key, rec), = ents.map_feed(wp, "wordpress", {})
    assert key == "hello" and rec["title"] == "Hello & welcome" and rec["excerpt"] == "Short"
    assert rec["content"] == "Long  body" and rec["image"].endswith("i.jpg")
    assert ents.feed_url("wordpress", "https://x.example").endswith("/wp-json/wp/v2/posts?per_page=50&_embed=1")


def test_validator_accepts_entity_and_content_bindings():
    m = default_manifest()
    reg = SiteApiRegistry("s", {})
    good = validate_plan({"regions": [
        {"component": "fb.pricing_table", "props": {"tiers": {"bind": "entity:Plan", "params": {"limit": 3}}}},
        {"id": "one", "component": "fb.feature_grid", "props": {"items": {"bind": "entity:Product",
                                                                          "params": {"key": "route.slug"}}}},
        {"id": "kb", "component": "fb.faq", "props": {"items": {"bind": "content:search",
                                                                  "params": {"query": "pricing"}}}},
        {"id": "w", "component": "fb.logos", "props": {"items": {"bind": "entity:Logo",
                                                                   "params": {"where": {"tier": "gold"}}}}},
    ]}, manifest=m, catalogue=reg)
    assert good.ok, good.problems
    for bad, expect in (({"bind": "entity:product"}, "entity type"), ({"bind": "content:search"}, "params.query"),
                        ({"bind": "entity:Plan", "map": {"title": "a b"}}, "map must be"),
                        ({"bind": "entity:Plan", "params": {"key": "route.Bad!"}}, "route parameter"),
                        ({"bind": "content:other"}, "binding must be")):
        rep = validate_plan({"regions": [{"component": "fb.faq", "props": {"items": bad}}]}, manifest=m, catalogue=reg)
        assert rep.plan.regions == [] and any(expect in p for p in rep.problems), rep.problems


def test_bind_entity_and_route_params():
    from app.experience.binding import bind_plan

    seen = []

    async def resolve(ref, params):
        seen.append((ref, params))
        if params.get("key"):
            return {"key": params["key"], "name": "Scale"}
        return [{"name": "Starter", "price": "₹999", "features": []}]

    m = default_manifest()
    rep = validate_plan({"regions": [
        {"id": "plans", "component": "fb.pricing_table", "props": {"tiers": {"bind": "entity:Plan"}}},
        {"id": "hero", "component": "fb.hero", "props": {"title": "x"}},
        {"id": "one", "component": "fb.media", "props": {"src": {"bind": "entity:Product", "path": "$.name",
                                                                  "params": {"key": "route.slug"}}}},
    ]}, manifest=m, catalogue=SiteApiRegistry("s", {}))
    bound = run(bind_plan(rep.plan, manifest=m, registry=SiteApiRegistry("s", {}),
                          ctx={"route": {"slug": "scale"}}, resolve=resolve))
    by = {b.id: b for b in bound}
    assert by["plans"].props["tiers"][0]["name"] == "Starter" and by["one"].props["src"] == "Scale"
    assert ("entity:Product", {"key": "scale"}) in seen
    # Without a resolver those bindings resolve to nothing (required → empty/error).
    bound2 = run(bind_plan(rep.plan, manifest=m, registry=SiteApiRegistry("s", {}), ctx={}))
    assert {b.id: b.state for b in bound2}["plans"] == "error"


# ---- P2-1: SSR -----------------------------------------------------------------

def test_render_sections_escape_and_fallbacks():
    hero = render_section({"type": "hero", "id": "hero", "component": "fb.hero", "state": "ready",
                           "props": {"title": "<script>x</script>", "cta_label": "Go", "action": "trial"}})
    assert "&lt;script&gt;" in hero and 'data-fb-region="hero"' in hero and 'data-fb-action="trial"' in hero
    form = render_section({"type": "enquiry_form", "id": "f", "component": "fb.enquiry_form",
                           "props": {"fields": [{"name": "email", "label": "Email", "type": "email"},
                                                {"name": "bad name!", "label": "x"}], "operation_id": "submitEnquiry"}},
                          form_action="https://api.example/experience/lead")
    assert 'method="post" action="https://api.example/experience/lead"' in form and "onsubmit" not in form
    assert 'name="email" type="email"' in form and 'name="badname"' in form and "data-fb-hydrate" in form
    wc = render_section({"type": "wc:acme-plan-table", "id": "p", "component": "acme.PlanTable",
                         "props": {"tiers": [{"name": "Scale", "price": "₹9"}], "note": '"><img>'}})
    assert "<acme-plan-table data-fb-props=" in wc and '<template shadowrootmode="open">' in wc
    assert "<li>Scale · ₹9</li>" in wc and '"><img>' not in wc
    assert render_section({"type": "wc:fb-evil", "props": {}}) == ""
    assert render_section({"type": "logos", "props": {"items": [{"src": "javascript:alert(1)"}]}}).count("<img") == 0
    assert "</script>" not in page_data_json({"x": "</script><b>"})


def test_render_document_head():
    html = render_document(fragment="<main></main>", css="body{}", data={"a": 1}, lang="en",
                           head={"title": "T & co", "description": "D", "canonical": "https://x.example/p",
                                 "robots": "noindex, follow", "json_ld": {"@type": "WebPage"}})
    assert "<title>T &amp; co</title>" in html and 'rel="canonical" href="https://x.example/p"' in html
    assert 'content="noindex, follow"' in html and 'id="fb-page-data"' in html and "ld+json" in html


# ---- P2-3: page planner ----------------------------------------------------------

class _Bridge:
    async def search(self, q, top_k=6):
        return [{"content": "Every plan includes online booking and reminders by SMS. Annual billing saves two months.",
                 "score": 0.9, "document_title": "Pricing"},
                {"content": "Patients book online at any hour, and reminders cut no-shows across the practice.",
                 "score": 0.9, "document_title": "Home"}]


class _DB:
    async def execute(self, *a, **k):
        class R:
            def all(self_inner):
                return []

            def first(self_inner):
                return None
        return R()


class _RT:
    class settings:
        cortex_confidence_threshold = 0.3

    def bridge(self, db, site_key):
        return _Bridge()


def test_page_planner_repairs_once_then_accepts():
    from app.ai.base import LLMResponse, ToolCall
    from app.experience.page_planner import build_page_plan

    calls = []

    class LLM:
        async def generate(self, **kw):
            calls.append(kw["messages"][0].text)
            if len(calls) == 1:  # an unknown component and an invented number
                regions = [{"id": "hero", "component": "fb.hero", "props": {"title": "Save 90% today"}},
                           {"id": "x", "component": "acme.Nope", "props": {}}]
            else:
                regions = [{"id": "hero", "component": "fb.hero", "props": {"title": "Plans that save two months"}},
                           {"id": "intro", "component": "fb.text", "props": {"body": "Book online at any hour."}}]
            return LLMResponse(tool_calls=[ToolCall("compose_page", {"title": "Pricing", "regions": regions})])

    out = run(build_page_plan(_DB(), _RT(), "s", Route("r", "/pricing", "Pricing", "Compare plans"), {},
                              Intent("compare-plans", "Comparing plans"), Signals(page="/pricing"),
                              manifest=default_manifest(), registry=SiteApiRegistry("s", {}), llm=LLM()))
    assert out["composer"] == "repaired" and len(calls) == 2
    assert "PREVIOUS PAGE HAD THESE PROBLEMS" in calls[1] and "acme.Nope" in calls[1]
    assert [r["id"] for r in out["plan"]["regions"]] == ["hero", "intro"]


def test_page_planner_rules_without_a_model():
    from app.experience.page_planner import build_page_plan

    out = run(build_page_plan(_DB(), _RT(), "s", Route("r", "/", "Home", "Introduce the product"), {},
                              Intent(), Signals(page="/"), manifest=default_manifest(),
                              registry=SiteApiRegistry("s", {})))
    assert out["composer"] == "rules"
    ids = [r["id"] for r in out["plan"]["regions"]]
    assert ids[0] == "hero" and "next" in ids


# ---- P2-4: patches ----------------------------------------------------------------

PLAN = {"plan_id": "pl_aaaaaaaaaa", "title": "P", "regions": [
    {"id": "hero", "component": "fb.hero", "props": {"title": "Hi"}},
    {"id": "intro", "component": "fb.text", "props": {"body": "Body"}},
    {"id": "faq", "component": "fb.faq", "props": {"items": [{"q": "a", "a": "b"}]}}]}


def test_apply_ops():
    new, ops, probs = apply_ops(PLAN, [
        {"op": "add", "region": "plans", "component": "fb.pricing_table", "props": {"tiers": []}, "before": "faq"},
        {"op": "replace", "region": "hero", "props": {"title": "Healthcare plans"}},
        {"op": "remove", "region": "intro"},
        {"op": "move", "region": "faq", "before": "hero"},
        {"op": "remove", "region": "ghost"}, {"op": "explode", "region": "x"}])
    assert [r["id"] for r in new["regions"]] == ["faq", "hero", "plans"]
    assert new["plan_id"] == PLAN["plan_id"] and PLAN["regions"][0]["props"]["title"] == "Hi"  # original untouched
    assert [o["op"] for o in ops] == ["add", "replace", "remove", "move"]
    assert ops[0]["animation"] == "fade" and ops[1]["animation"] == "highlight" and ops[3]["before"] == "hero"
    assert len(probs) == 2
    assert "ON-SCREEN PAGE (plan pl_aaaaaaaaaa)" in outline(PLAN) and "patch_plan" in outline(PLAN)


def test_thinker_patch_plan_binds_only_what_changed():
    from app.config import get_settings
    from app.orchestrator.thinker import HeavyThinker, ThinkResult

    t = HeavyThinker(None, get_settings())
    result = ThinkResult()
    out = run(t._patch_plan({"ops": [
        {"op": "replace", "region": "hero", "props": {"title": "Healthcare plans"}},
        {"op": "add", "region": "cta", "component": "fb.cta", "props": {"title": "Book", "cta_label": "Go"}},
        {"op": "add", "region": "bad", "component": "fb.text", "props": {}},
        {"op": "remove", "region": "faq"}]}, "nosuch-site", _Bridge(), result, PLAN, {"site_key": "nosuch-site"}))
    assert out["ok"] and out["plan_id"] == PLAN["plan_id"]
    patch = result.plan_patches[0]
    ops = {o["region"]: o for o in patch.ops}
    assert set(ops) == {"hero", "cta", "faq"}
    assert ops["hero"]["section"]["props"]["title"] == "Healthcare plans" and ops["faq"]["op"] == "remove"
    assert "intro" not in ops  # unchanged regions are not re-sent
    assert [r["id"] for r in patch.plan["regions"]] == ["hero", "intro", "cta"]
    assert any("bad" in p for p in out["problems"])
    none = run(t._patch_plan({"ops": [{"op": "remove", "region": "x"}]}, "s", _Bridge(), ThinkResult(), None, {}))
    assert none["ok"] is False


# ---- API ------------------------------------------------------------------------------

def _site(client, domain=None):
    body = client.post("/auth/register", json={"email": f"pg_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": "supersecret1"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Orbit", **({"domain": domain} if domain else {})},
                       headers=h).json()
    w = f"/tenant/websites/{site['id']}"
    assert client.post(f"{w}/sources", headers=h, json={"kind": "text", "name": "Orbit",
                                                        "content": KNOWLEDGE}).status_code == 201
    assert client.post(f"{w}/ingestion/run?wait=true", headers=h).json()["status"] == "done"
    return h, site, w


def test_routes_entities_pages_and_canonical():
    from app.main import app

    with TestClient(app) as client:
        h, site, w = _site(client, domain="orbit.example")
        assert client.post(f"{w}/routes", headers=h, json={"pattern": "products/x y"}).status_code == 422
        home = client.post(f"{w}/routes", headers=h, json={"pattern": "/", "title": "Home",
                                                           "purpose": "Introduce Orbit"}).json()
        prod = client.post(f"{w}/routes", headers=h, json={"pattern": "/products/:slug", "title": "Product"}).json()
        assert client.put(f"{w}/routes/{home['id']}", headers=h, json={"pattern": "/other"}).status_code == 422

        # Entities: import, list, single record, delete.
        imp = client.post(f"{w}/entities/import", headers=h, json={
            "type": "Product", "format": "json", "key_field": "slug",
            "content": json.dumps([{"slug": "scale", "name": "Scale", "price": "₹9,999"},
                                   {"slug": "starter", "name": "Starter"}])}).json()
        assert imp["imported"] == 2
        assert client.get(f"{w}/entities", headers=h).json()["types"] == [{"type": "Product", "count": 2}]
        assert client.put(f"{w}/entities/Product/solo", headers=h, json={"data": {"name": "Solo"}}).status_code == 200
        assert client.put(f"{w}/entities/product/x", headers=h, json={"data": {}}).status_code == 422
        assert len(client.get(f"{w}/entities/Product", headers=h).json()["records"]) == 3
        assert client.delete(f"{w}/entities/Product/solo", headers=h).status_code == 204

        key = site["public_key"]
        # No route → 404 body.
        assert client.get(f"/experience/page?key={key}&path=/nothing").json()["status"] == 404
        # First visitor: a rules page now, their plan building in the background.
        first = client.get(f"/experience/page?key={key}&path=/").json()
        assert first["status"] == 200 and first["route"] == "/" and first["pending"]
        assert 'data-fb-region="hero"' in first["html"] and first["head"]["canonical"] == "https://orbit.example/"
        assert first["head"]["robots"] == "noindex, follow" and first["plan_id"].startswith("pl_")
        assert "fbpage-hero-title" in first["html"] and ":root{" in first["css"]
        # Restore a specific plan by ?fbv.
        again = client.get(f"/experience/page?key={key}&path=/&fbv={first['plan_id']}").json()
        assert again["restored"] and again["plan_id"] == first["plan_id"] and again["head"]["robots"].startswith("noindex")

        # Console: generate, set canonical; crawlers get it, indexed.
        gen = client.post(f"{w}/routes/{home['id']}/generate", headers=h, json={"family": "general"})
        assert gen.status_code == 201 and "<section data-region='hero'>" in gen.json()["preview_html"]
        canon = client.put(f"{w}/routes/{home['id']}/canonical", headers=h, json={"plan": gen.json()["id"]}).json()
        assert canon["canonical_plan"] == gen.json()["id"]
        bot = client.get(f"/experience/page?key={key}&path=/&ua=Googlebot/2.1").json()
        assert bot["served"] == "canonical" and bot["head"]["robots"] == "index, follow"
        assert bot["plan_id"] == gen.json()["plan_id"]

        # A templated route bound to an entity record by its slug.
        from app.db import session_scope
        from app.experience import regions_store as rs
        from app.experience.routes_store import PAGE_REGIONS

        async def seed():
            async with session_scope() as db:
                await rs.store_plan(db, site["site_key"], key="prodplan", family="general", persona="", lang="en",
                                    page="/products/:slug", regions=[PAGE_REGIONS], content_version="x",
                                    manifest_version=None, composer="rules", build_ms=1, plan={
                                        "plan_id": "pl_bbbbbbbbbb", "title": "Product", "regions": [
                                            {"id": "hero", "component": "fb.hero",
                                             "props": {"title": "Our product"}},
                                            {"id": "detail", "component": "fb.feature_grid", "props": {
                                                "items": {"bind": "entity:Product", "params": {"limit": 5},
                                                          "map": {"title": "name", "body": "price"}}}}]})
                await rs.set_plan_status(db, site["site_key"], (await rs.cached_plan(db, site["site_key"], "prodplan"))["id"], "pinned")
        client.portal.call(seed)
        p = client.get(f"/experience/page?key={key}&path=/products/scale").json()
        assert p["status"] == 200 and p["params"] == {"slug": "scale"}
        assert p["served"] == "pinned" and "Starter" in p["html"] and "Scale" in p["html"]
        assert "₹9,999" in p["html"]  # mapped price → body

        # Hosted shell: full document, CSP, page data, canonical.
        doc = client.get(f"/g/{site['site_key']}/")
        assert doc.status_code == 200 and "<!doctype html>" in doc.text and 'id="fb-page-data"' in doc.text
        assert "frame-ancestors 'none'" in doc.headers["content-security-policy"]
        assert "fluid-buddha-composed.global.js" in doc.text and "/widget/loader.js" in doc.text
        assert client.get(f"/g/{site['site_key']}/nope/really").status_code == 404

        # The no-JavaScript form posts a lead and goes back.
        lead = client.post("/experience/lead", data={"key": key, "email": "visitor@example.com",
                                                      "message": "Call me", "_return": "/pricing"},
                           follow_redirects=False)
        assert lead.status_code == 303 and lead.headers["location"] == "/pricing#sent"
        off = client.post("/experience/lead", data={"key": key, "email": "v@example.com",
                                                     "_return": "https://evil.example/x"}, follow_redirects=False)
        assert off.status_code == 200 and "Thank you" in off.text  # never redirects off-site

        assert client.delete(f"{w}/routes/{prod['id']}", headers=h).status_code == 204


@dataclass
class _Got:
    url: str
    text: str


def test_connectors_sync_with_a_fake_feed(monkeypatch):
    from app.main import app
    from app.routes import pages as pages_route

    feed = {"items": [{"slug": "a", "title": "A"}, {"slug": "b", "title": "B"}]}

    async def fake_fetch(url, **_):
        return _Got(url, json.dumps(feed))

    monkeypatch.setattr(pages_route, "fetch_public", fake_fetch)
    monkeypatch.setattr(pages_route, "check_url", lambda u: ("x", 443))
    with TestClient(app) as client:
        h, site, w = _site(client)
        assert client.post(f"{w}/connectors", headers=h, json={"kind": "json_feed", "url": "http://insecure.example",
                                                               "entity_type": "Post"}).status_code == 422
        c = client.post(f"{w}/connectors", headers=h, json={
            "kind": "json_feed", "name": "Blog", "url": "https://cms.example/posts.json", "entity_type": "Post",
            "items_path": "$.items[*]", "key_field": "slug"}).json()
        r = client.post(f"{w}/connectors/{c['id']}/sync", headers=h).json()
        assert r["records"] == 2 and r["status"].startswith("ok")
        feed["items"] = [{"slug": "b", "title": "B2"}]
        client.post(f"{w}/connectors/{c['id']}/sync", headers=h)
        recs = client.get(f"{w}/entities/Post", headers=h).json()["records"]
        assert [(x["key"], x["data"]["title"]) for x in recs] == [("b", "B2")]  # 'a' left the feed
        listed = client.get(f"{w}/connectors", headers=h).json()["connectors"]
        assert listed[0]["last_status"].startswith("ok") and listed[0]["last_sync_at"]
        assert client.delete(f"{w}/connectors/{c['id']}", headers=h).status_code == 204
        assert client.get(f"{w}/entities/Post", headers=h).json()["records"] == []
