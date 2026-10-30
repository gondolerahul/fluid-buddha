"""
Admin conversation-cache view/edit tests (Phase 5, req E/G).

    MOCK_AI=true python -m pytest tests/test_cache_admin.py -q

Seeds cache turns through the runtime in a self-contained loop (engine disposed
after, mirroring tests/test_cache.py) so the TestClient's pool gets fresh
loop-bound connections, then exercises the list/get/edit/delete routes.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.cortex.episodic import EpisodicCache
from app.cortex.providers import build_cortex_providers
from app.db import dispose_engine, init_db, session_scope


def _run(coro):
    async def wrapper():
        try:
            return await coro
        finally:
            await dispose_engine()
    return asyncio.run(wrapper())


async def _seed(site_key: str) -> None:
    await init_db()
    settings = get_settings()
    providers = build_cortex_providers(settings)
    async with session_scope() as db:
        cache = EpisodicCache(db, settings, providers, site_key=site_key)
        await cache.record(
            question="What is your refund policy?", answer_text="30-day money back.",
            components=[], actions=[{"type": "navigate", "path": "/refunds"}],
            persona="startups", page="/", channel="text",
        )
        await cache.record(
            question="Do you support SSO?", answer_text="Yes, SAML SSO on Enterprise.",
            components=[], actions=[], persona="enterprise", page="/security", channel="voice",
        )


def test_cache_admin_full_crud():
    """Create a website, seed cache under its real site_key, then CRUD via API."""
    from app.main import app

    # Create the website first to learn its generated site_key.
    with TestClient(app) as client:
        email = f"caf_{uuid.uuid4().hex[:10]}@example.com"
        tok = client.post("/auth/register",
                          json={"email": email, "password": "supersecret1"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        site = client.post("/tenant/websites", json={"name": "Cache Full"}, headers=h).json()
        wid, site_key = site["id"], site["site_key"]
        # fresh site has no cached turns yet
        assert client.get(f"/tenant/websites/{wid}/cache", headers=h).json()["total"] == 0

    # Seed that key in a clean loop (disposes the engine afterwards).
    _run(_seed(site_key))

    with TestClient(app) as client:
        tok = client.post("/auth/login",
                          json={"email": email, "password": "supersecret1"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}

        listing = client.get(f"/tenant/websites/{wid}/cache", headers=h).json()
        assert listing["total"] == 2
        eid = next(i["id"] for i in listing["items"] if "refund" in i["question"].lower())

        # edit the stored answer + actions (saved to cache, req E)
        upd = client.put(f"/tenant/websites/{wid}/cache/{eid}", json={
            "answer_text": "We offer a 45-day money-back guarantee.",
            "actions": [{"type": "navigate", "path": "/guarantee"}],
        }, headers=h)
        assert upd.status_code == 200
        assert upd.json()["answer_text"].startswith("We offer a 45-day")
        assert upd.json()["actions"][0]["path"] == "/guarantee"

        # search + delete
        assert client.get(f"/tenant/websites/{wid}/cache?search=SSO", headers=h).json()["total"] == 1
        assert client.delete(f"/tenant/websites/{wid}/cache/{eid}", headers=h).status_code == 204
        assert client.get(f"/tenant/websites/{wid}/cache/{eid}", headers=h).status_code == 404

        # tenant isolation
        t2 = client.post("/auth/register", json={
            "email": f"o_{uuid.uuid4().hex[:8]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        assert client.get(f"/tenant/websites/{wid}/cache",
                          headers={"Authorization": f"Bearer {t2}"}).status_code == 404
