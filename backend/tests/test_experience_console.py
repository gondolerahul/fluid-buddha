"""Generative experience, Phase 0 console side (P0-7 design system and manifest
versions, P0-8 Web Component entries, P0-9 draft generation)."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.auth import roles
from app.experience import drafts
from app.experience.manifest import clear_manifest_cache, load_manifest, parse_manifest

SRI = "sha384-" + "A" * 64
BUNDLE = {"url": "https://cdn.acme.example/fb-components.js", "integrity": SRI}


def _tenant(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"xp_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _site(client: TestClient, h: dict) -> tuple[str, str]:
    site = client.post("/tenant/websites", json={"name": "XP Co"}, headers=h).json()
    return site["id"], site["site_key"]


# ---- P0-8: Web Component entries -------------------------------------------

def test_wc_entries_need_a_valid_tag_and_bundle():
    m, problems = parse_manifest({"components": [
        {"id": "acme.PlanTable", "renderer": "wc:acme-plan-table"}]})
    assert m.get("acme.PlanTable") is None and any("needs the manifest's bundle" in p for p in problems)

    m, problems = parse_manifest({"bundle": BUNDLE, "components": [
        {"id": "acme.PlanTable", "renderer": "wc:acme-plan-table"},
        {"id": "acme.Bad", "renderer": "wc:notag"},
        {"id": "acme.Ours", "renderer": "wc:fluid-buddha-x"},
        {"id": "acme.PlanTable", "renderer": "hero"},
    ]})
    assert m.get("acme.PlanTable").renderer == "wc:acme-plan-table" and m.bundle == BUNDLE
    assert m.get("acme.Bad") is None and m.get("acme.Ours") is None
    assert any("duplicate" in p for p in problems)

    for bad in ({"url": "http://x.example/a.js", "integrity": SRI},
                {"url": "https://x.example/a.js", "integrity": "md5-abc"},
                {"url": "https://x.example/a.js\"><script>", "integrity": SRI}):
        _, problems = parse_manifest({"bundle": bad})
        assert problems, bad


def test_compose_page_carries_the_bundle_for_wc_sections():
    from app.experience.compose import compose_page
    from app.experience.manifest import remember_approved

    remember_approved("wc-site", {"bundle": BUNDLE, "components": [
        {"id": "acme.Hero", "renderer": "wc:acme-hero",
         "props": {"headline": {"type": "string", "source": "model_text", "required": True}}}]}, 3)
    try:
        page, result = asyncio.run(compose_page({"title": "T", "regions": [
            {"component": "acme.Hero", "props": {"headline": "Hello"}},
            {"component": "fb.text", "props": {"body": "b"}}]}, site_key="wc-site", sync_id="page_x"))
        wire = page.to_dict()
        assert wire["sections"][0]["type"] == "wc:acme-hero" and wire["bundle"] == BUNDLE
        assert page.plan["provenance"]["manifest"] == "console"
        assert page.plan["provenance"]["manifest_version"] == 3
        page2, _ = asyncio.run(compose_page({"title": "T", "regions": [
            {"component": "fb.text", "props": {"body": "b"}}]}, site_key="wc-site", sync_id="page_y"))
        assert "bundle" not in page2.to_dict()  # only sent when a WC section is drawn
    finally:
        clear_manifest_cache()


# ---- P0-7: role rules -------------------------------------------------------

def test_role_rules():
    assert roles.required_role("POST", "/tenant/websites/abc/manifest/versions/3/approve") == "admin"
    assert roles.required_role("POST", "/tenant/websites/abc/manifest/versions") == "editor"
    assert roles.required_role("PUT", "/tenant/websites/abc/design-system") == "editor"
    assert roles.required_role("GET", "/tenant/websites/abc/manifest") == "viewer"


# ---- P0-7: design system API ------------------------------------------------

def test_design_system_put_get_delete():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid, site_key = _site(client, h)
        base = f"/tenant/websites/{wid}/design-system"
        first = client.get(base, headers=h).json()
        assert first["current"] is None and first["source"] in ("default", "extracted")

        body = {"name": "XP", "colors": {"primary": "#112233"}, "radius": "8px",
                "typography": {"font_family": "Inter, sans-serif", "scale": 1.2},
                "brand_voice": "Plain.",
                "tunables": {"density": {"allowed": ["airy", "compact"], "default": "airy"}}}
        saved = client.put(base, json=body, headers=h)
        assert saved.status_code == 200, saved.text
        doc = saved.json()
        assert doc["source"] == "console"
        assert doc["effective"]["tokens"]["--ds-color-primary"] == "#112233"
        assert doc["effective"]["tunables"]["density"]["allowed"] == ["airy", "compact"]
        # The public endpoint the widget themes from serves it too.
        pub = client.get(f"/design-system?site={site_key}").json()
        assert pub["colors"]["primary"] == "#112233"

        for bad in ({"colors": {"primary": "red; background:url(x)"}},
                    {"logo_url": "http://insecure.example/logo.png"},
                    {"radius": "calc(1px)"},
                    {"tunables": {"price": {"allowed": ["low"]}}},
                    {"typography": {"font_family": "x;}</style>"}}):
            assert client.put(base, json=bad, headers=h).status_code == 422, bad

        back = client.delete(base, headers=h).json()
        assert back["current"] is None and back["source"] != "console"


# ---- P0-7: manifest versions API --------------------------------------------

def test_manifest_versions_draft_approve_archive():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid, site_key = _site(client, h)
        base = f"/tenant/websites/{wid}/manifest"
        empty = client.get(base, headers=h).json()
        assert empty["active"] is None and empty["source"] == "default"

        bad = client.post(f"{base}/versions", headers=h, json={"data": {"components": [
            {"id": "acme.Plan", "renderer": "wc:acme-plan"}]}})
        assert bad.status_code == 201
        v1 = bad.json()
        assert v1["version"] == 1 and v1["status"] == "draft"
        assert any("bundle" in p for p in v1["check"]["problems"])
        # A draft with problems can't be approved.
        refused = client.post(f"{base}/versions/1/approve", headers=h)
        assert refused.status_code == 422 and refused.json()["detail"]["problems"]

        # Fix the draft in place, then approve it.
        fixed = client.put(f"{base}/versions/1", headers=h, json={"notes": "with bundle", "data": {
            "bundle": BUNDLE, "components": [
                {"id": "acme.Plan", "renderer": "wc:acme-plan", "purpose": "Plans",
                 "props": {"tiers": {"type": "array", "source": "binding_only", "required": True}}}]}})
        assert fixed.status_code == 200 and not fixed.json()["check"]["problems"]
        ok = client.post(f"{base}/versions/1/approve", headers=h)
        assert ok.status_code == 200 and ok.json()["status"] == "approved"
        assert ok.json()["approved_by"]

        # The planner now sees the approved version.
        assert load_manifest(site_key).get("acme.Plan") is not None
        assert load_manifest(site_key).source == "console"

        # Approved versions are immutable and can't be deleted.
        assert client.put(f"{base}/versions/1", headers=h, json={"data": {}}).status_code == 409
        assert client.delete(f"{base}/versions/1", headers=h).status_code == 409

        # A second approval archives the first.
        v2 = client.post(f"{base}/versions", headers=h, json={"data": {"components": [
            {"id": "acme.Intro", "renderer": "hero"}]}}).json()
        assert v2["version"] == 2
        assert client.post(f"{base}/versions/2/approve", headers=h).status_code == 200
        view = client.get(base, headers=h).json()
        statuses = {v["version"]: v["status"] for v in view["versions"]}
        assert statuses == {1: "archived", 2: "approved"} and view["active_version"] == 2
        assert load_manifest(site_key).get("acme.Plan") is None

        # Drafts can be deleted; unknown versions 404.
        v3 = client.post(f"{base}/versions", headers=h, json={"data": {}}).json()
        assert client.delete(f"{base}/versions/{v3['version']}", headers=h).status_code == 204
        assert client.get(f"{base}/versions/99", headers=h).status_code == 404
        assert client.post(f"{base}/versions", headers=h, json={"data": []}).status_code == 422
    clear_manifest_cache()


def test_manifest_is_per_tenant():
    from app.main import app

    with TestClient(app) as client:
        h1, h2 = _tenant(client), _tenant(client)
        wid, _ = _site(client, h1)
        assert client.get(f"/tenant/websites/{wid}/manifest", headers=h2).status_code == 404
        assert client.put(f"/tenant/websites/{wid}/design-system", headers=h2,
                          json={"name": "x"}).status_code == 404


# ---- P0-9: drafts -----------------------------------------------------------

STORYBOOK_INDEX = {"v": 5, "entries": {
    "marketing-pricingtable--default": {"type": "story", "id": "marketing-pricingtable--default",
                                        "title": "Marketing/PricingTable", "name": "Default"},
    "marketing-pricingtable--annual": {"type": "story", "id": "marketing-pricingtable--annual",
                                       "title": "Marketing/PricingTable", "name": "Annual billing",
                                       "argTypes": {
                                           "title": {"type": {"name": "string"}},
                                           "plans": {"type": {"name": "array", "required": True}},
                                           "period": {"control": "select", "options": ["monthly", "annual"]},
                                           "onSelect": {"type": {"name": "function"}},
                                       }},
    "marketing-pricingtable--docs": {"type": "docs", "id": "marketing-pricingtable--docs",
                                     "title": "Marketing/PricingTable", "name": "Docs"},
    "basics-herobanner--default": {"type": "story", "id": "basics-herobanner--default",
                                   "title": "Basics/HeroBanner", "name": "Default"},
}}

DOCGEN = [{"displayName": "HeroBanner", "props": {
    "headline": {"tsType": {"name": "string"}, "required": True},
    "items": {"tsType": {"name": "Array", "raw": "Item[]"}},
    "onClick": {"tsType": {"name": "signature", "raw": "() => void"}},
    "className": {"tsType": {"name": "string"}},
}}]


def test_draft_from_storybook():
    d = drafts.draft_from_storybook(STORYBOOK_INDEX, site_key="acme-co", docgen=DOCGEN)
    comps = {c["id"]: c for c in d["data"]["components"]}
    assert set(comps) == {"acmeco.PricingTable", "acmeco.HeroBanner"}
    pt = comps["acmeco.PricingTable"]
    assert pt["renderer"] == "wc:acmeco-pricing-table"
    assert pt["props"]["title"] == {"type": "string", "source": "model_text"}
    assert pt["props"]["plans"]["type"] == "array" and pt["props"]["plans"]["required"]
    assert pt["props"]["period"]["enum"] == ["monthly", "annual"]
    assert "onSelect" not in pt["props"]
    assert pt["use_when"] == ["default", "annual-billing"]
    hb = comps["acmeco.HeroBanner"]["props"]
    assert hb["headline"]["required"] and hb["items"]["type"] == "array"
    assert "onClick" not in hb and "className" not in hb
    assert "bundle" in d["notes"]
    # A draft with WC entries is not approvable until the bundle is added.
    _, problems = parse_manifest(d["data"])
    assert any("needs the manifest's bundle" in p for p in problems)
    _, problems = parse_manifest({**d["data"], "bundle": BUNDLE})
    assert problems == []


PAGES = [
    ("https://acme.example/", """<html><body>
        <section class="hero hero--dark"><h1>Hi</h1></section>
        <div id="features" class="grid"></div>
        <section class="pricing-table"></section>
        <section class="testimonials"></section>
        <footer class="site-footer"></footer></body></html>"""),
    ("https://acme.example/pricing", """<section class="pricing-table"></section>
        <section class="faq-list"></section><section class="cta-banner"></section>"""),
]


def test_draft_from_pages():
    d = drafts.draft_from_pages(PAGES, site_key="acme")
    by_renderer = {c["renderer"]: c for c in d["data"]["components"]}
    assert {"hero", "feature_grid", "pricing_table", "testimonials", "faq", "cta"} <= set(by_renderer)
    pricing = by_renderer["pricing_table"]
    assert pricing["id"] == "acme.PricingTable" and "2 pages" in pricing["purpose"]
    assert sorted(pricing["use_when"]) == ["home", "pricing"]
    assert pricing["props"]["tiers"]["required"]
    _, problems = parse_manifest(d["data"])
    assert problems == []


@dataclass
class _Got:
    url: str
    text: str


def test_fetch_helpers_with_a_fake_fetch():
    site = {
        "https://acme.example/": '<a href="/pricing">P</a><a href="https://other.example/">x</a>'
                                 '<section class="hero"></section>',
        "https://acme.example/pricing": '<section class="faq"></section>',
    }

    async def fetch(url, **_):
        if url in site:
            return _Got(url, site[url])
        if url.endswith("index.json"):
            raise ValueError("404")
        if url.endswith("stories.json"):
            return _Got(url, '{"v": 3, "stories": {"a": {"title": "X/Card", "name": "Default"}}}')
        raise ValueError("404")

    pages = asyncio.run(drafts.fetch_site_pages("https://acme.example/", fetch, 5))
    assert [u for u, _ in pages] == ["https://acme.example/", "https://acme.example/pricing"]
    index = asyncio.run(drafts.fetch_storybook_index("https://sb.acme.example", fetch))
    assert index["v"] == 3
    d = drafts.draft_from_storybook(index, site_key="acme")
    assert d["data"]["components"][0]["id"] == "acme.Card"


def test_storybook_draft_endpoint_with_uploaded_index():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid, _ = _site(client, h)
        res = client.post(f"/tenant/websites/{wid}/manifest/drafts/storybook", headers=h,
                          json={"index": STORYBOOK_INDEX, "docgen": DOCGEN})
        assert res.status_code == 201, res.text
        v = res.json()
        assert v["source"] == "storybook" and v["status"] == "draft"
        assert len(v["check"]["components"]) == 0  # WC entries wait for the bundle
        assert any("bundle" in p for p in v["check"]["problems"])
        none = client.post(f"/tenant/websites/{wid}/manifest/drafts/storybook", headers=h,
                           json={"index": {"v": 5, "entries": {}}})
        assert none.status_code == 422
        assert client.post(f"/tenant/websites/{wid}/manifest/drafts/storybook", headers=h,
                           json={}).status_code == 422
        # Private addresses are refused before any fetch.
        assert client.post(f"/tenant/websites/{wid}/manifest/drafts/site", headers=h,
                           json={"url": "http://127.0.0.1:8080"}).status_code == 422
