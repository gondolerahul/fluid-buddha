"""
Per-site agent profile — the tenant brain (docs/defects.md D-9; roadmap Phase 0
"De-HireBuddha the brain").

- HireBuddha's built-in profile reproduces the old hard-coded brain exactly.
- Any other site gets a neutral brain: no HireBuddha copy, no personas, no routes.
- A stored profile drives the prompts, the set_persona tool, navigation and the
  guided tour.
- Ingested URLs become routes; the admin API reads/edits the profile.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.main import app
from app.orchestrator import profile as prof
from app.orchestrator.personas import persona_fragment, valid_personas
from app.orchestrator.profile import Persona, SiteProfile, default_profile, profile_for
from app.orchestrator.prompts import (
    build_lean_system,
    build_reaction_system,
    build_router_system,
    build_thinker_system,
)
from app.orchestrator.sitemap import resolve_route, route_from_url
from app.orchestrator.tools import tools_for
from app.orchestrator.tour import _fallback_plan


def _set_persona_tool(level: str, site: str | None):
    return next((t for t in tools_for(level, site) if t.name == "set_persona"), None)


@pytest.fixture
def custom_profile():
    """A cached tenant profile, evicted after the test."""
    p = SiteProfile(
        site_key=f"zeta-{uuid.uuid4().hex[:6]}",
        company_name="Zeta Labs",
        agent_name="Nova",
        brand_voice="calm and precise",
        personas=[Persona(slug="devs", label="Developers", focus="APIs", tone="technical")],
        closing_use_case="Zeta saves your team hours every week.",
        routes=["/", "/pricing", "/docs/api"],
    )
    prof.remember(p)
    yield p
    prof.invalidate(p.site_key)


# ---- HireBuddha keeps its brain --------------------------------------------

def test_hirebuddha_profile_reproduces_legacy_brain():
    p = default_profile("hirebuddha")
    assert (p.agent_name, p.company_name) == ("Pragya", "HireBuddha")
    assert p.persona_slugs == ["startups", "solopreneurs", "medium-enterprise", "enterprise"]
    assert "/pricing" in p.routes and "/blog/" in p.dynamic_prefixes

    router = build_router_system("hirebuddha")
    assert 'Allowed: "startups" | "solopreneurs" | "medium-enterprise" | "enterprise".' in router
    thinker = build_thinker_system(None, "hirebuddha")
    assert "You are Pragya" in thinker and "HireBuddha website" in thinker
    assert "VALID ROUTES" in thinker
    assert resolve_route("hirebuddha", "/pricing") == "/pricing"
    assert _set_persona_tool("advance", "hirebuddha").parameters["properties"]["persona"]["enum"] \
        == p.persona_slugs
    assert "Startups & SMEs" in persona_fragment("startups", "hirebuddha")


# ---- other sites get a neutral brain ---------------------------------------

def test_unconfigured_site_gets_neutral_brain():
    site = f"acme-co-{uuid.uuid4().hex[:4]}"
    p = profile_for(site)
    assert p.company_name.startswith("Acme Co") and p.personas == [] and p.routes == []

    for prompt in (
        build_router_system(site),
        build_thinker_system(None, site),
        build_lean_system(None, site, []),
        build_reaction_system(None, site, "roi_calculator", {}),
    ):
        assert "HireBuddha" not in prompt
    assert "always null" in build_router_system(site)
    assert _set_persona_tool("advance", site) is None
    assert valid_personas(site) == []
    assert resolve_route(site, "/pricing") is None  # no routes known yet


# ---- a stored profile drives everything ------------------------------------

def test_custom_profile_drives_prompts_tools_navigation_and_tour(custom_profile):
    site = custom_profile.site_key
    thinker = build_thinker_system("devs", site)
    assert "You are Nova" in thinker and "Zeta Labs website" in thinker
    assert "calm and precise" in thinker and "Pragya" not in thinker
    assert "'Developers' segment" in thinker
    assert '"devs"' in build_router_system(site)
    assert "Nova" in build_lean_system(None, site, [])

    tool = _set_persona_tool("high", site)
    assert tool.parameters["properties"]["persona"]["enum"] == ["devs"]

    assert resolve_route(site, "/docs/api") == "/docs/api"
    assert resolve_route(site, "/pricng") == "/pricing"  # close guess snaps
    assert resolve_route(site, "/careers") is None       # unknown page dropped

    plan = _fallback_plan(site, [{"route": "/", "title": "Home", "summary": "Zeta."}])
    assert "Nova" in plan.stops[0].narration
    assert plan.stops[-1].narration == "Zeta saves your team hours every week."


def test_route_from_url():
    assert route_from_url("https://acme.com/pricing/?plan=pro#top") == "/pricing"
    assert route_from_url("https://acme.com") == "/"
    assert route_from_url("https://acme.com/docs/api/") == "/docs/api"


def test_merge_routes_adds_without_duplicates():
    site = f"merge-{uuid.uuid4().hex[:6]}"

    async def run() -> list[str]:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                await prof.merge_routes(db, site, ["/a", "/b/"])
                await prof.merge_routes(db, site, ["/a", "/c?x=1"])
                routes = (await prof.load_profile(db, site)).routes
                await db.execute(text("DELETE FROM site_profiles WHERE site_key = :k"), {"k": site})
                await db.commit()
                return routes
        finally:
            await engine.dispose()
            prof.invalidate(site)

    assert asyncio.run(run()) == ["/a", "/b", "/c"]


# ---- admin API ---------------------------------------------------------------

def _register(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"ap_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_profile_api_read_edit_validate_and_isolate():
    with TestClient(app) as client:
        h = _register(client)
        site = client.post("/tenant/websites", json={"name": "Orbit Co"}, headers=h).json()
        url = f"/tenant/websites/{site['id']}/profile"

        # Default: neutral brain named after the website.
        p = client.get(url, headers=h).json()
        assert p["company_name"] == "Orbit Co" and p["agent_name"] == "Pragya"
        assert p["personas"] == [] and p["routes"] == []

        # Partial edit.
        r = client.put(url, headers=h, json={
            "agent_name": "Ava",
            "personas": [{"slug": "founders", "label": "Founders", "landing": "/start"}],
            "routes": ["/pricing", "/docs/"],
        })
        assert r.status_code == 200, r.text
        p = client.get(url, headers=h).json()
        assert p["agent_name"] == "Ava" and p["company_name"] == "Orbit Co"
        assert [x["slug"] for x in p["personas"]] == ["founders"]
        assert p["routes"] == ["/pricing", "/docs"]

        # The live brain picks it up.
        assert profile_for(site["site_key"]).agent_name == "Ava"
        assert resolve_route(site["site_key"], "/docs") == "/docs"
        assert client.post("/chat", json={"message": "hello", "key": site["public_key"]}).status_code == 200

        # Validation.
        assert client.put(url, headers=h, json={"routes": ["pricing"]}).status_code == 422
        assert client.put(url, headers=h, json={"personas": [
            {"slug": "a", "label": "A"}, {"slug": "a", "label": "B"}]}).status_code == 422
        assert client.put(url, headers=h, json={"personas": [
            {"slug": "Bad Slug", "label": "X"}]}).status_code == 422

        # Another tenant can't read or edit it.
        other = _register(client)
        assert client.get(url, headers=other).status_code == 404
        assert client.put(url, headers=other, json={"agent_name": "Mallory"}).status_code == 404

        # Deleting the website removes the profile too.
        assert client.delete(f"/tenant/websites/{site['id']}", headers=h).status_code == 204
        assert profile_for(site["site_key"]).agent_name == "Pragya"  # cache evicted
