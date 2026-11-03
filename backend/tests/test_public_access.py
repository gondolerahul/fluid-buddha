"""
Public-surface lockdown tests (docs/defects.md D-1, D-4).

- A registered tenant site can't be reached by raw site_key — it needs its
  widget key, which resolves the site and tier server-side.
- Built-in demo sites stay open.
- A tenant can't register a website under a reserved built-in key.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.security import hash_password
from app.config import get_settings
from app.main import app
from app.tenancy import store
from app.tenancy.public_access import PublicAccessError, resolve_public_site


def _register(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"pa_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_registered_site_requires_widget_key():
    with TestClient(app) as client:
        h = _register(client)
        site = client.post("/tenant/websites", json={"name": "Guard Co"}, headers=h).json()
        pk, sk = site["public_key"], site["site_key"]
        assert pk and pk.startswith("fbk_")

        # With the key: allowed.
        assert client.post("/chat", json={"message": "hi", "key": pk}).status_code == 200
        # By raw site_key, no key: refused.
        r = client.post("/chat", json={"message": "hi", "site": sk})
        assert r.status_code == 403 and r.json()["detail"] == "widget_key_required"
        # A bogus key: refused.
        assert client.post("/chat", json={"message": "hi", "key": "fbk_nope"}).status_code == 403
        # A built-in demo site stays open without a key.
        assert client.post("/chat", json={"message": "hi", "site": "hirebuddha"}).status_code == 200


def test_ws_registered_site_requires_key():
    with TestClient(app) as client:
        h = _register(client)
        site = client.post("/tenant/websites", json={"name": "WS Guard Co"}, headers=h).json()
        sk = site["site_key"]
        with client.websocket_connect(f"/ws/voice?site={sk}") as ws:
            msg = ws.receive_json()
            assert msg["channel"] == "EVENTS" and msg["type"] == "error"
            assert msg["payload"]["reason"] == "widget_key_required"


def test_reserved_site_key_cannot_be_registered():
    with TestClient(app) as client:
        h = _register(client)
        site = client.post("/tenant/websites", json={"name": "HireBuddha"}, headers=h).json()
        assert site["site_key"] != "hirebuddha"


def test_resolver_locks_site_and_tier():
    """The widget key pins the site + the tenant's tier; the client tier is ignored."""
    async def run() -> None:
        # Throwaway engine (NullPool) created and disposed in this loop, so it
        # never touches the app's shared async pool. See tests/conftest.py.
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session() as db:
                tenant = await store.create_tenant(
                    db, email=f"res_{uuid.uuid4().hex[:8]}@example.com",
                    password_hash=hash_password("supersecret1"),
                )
                site = await store.create_website(
                    db, tenant_id=tenant.id, name="Resolver Co", intelligence="high",
                )

                # Key path: tier locked to the tenant's "high"; client "extreme" ignored.
                keyed = await resolve_public_site(
                    db, key=site.public_key, site="whatever",
                    intelligence="extreme", origin=None,
                )
                assert keyed.tier_locked
                assert keyed.site_key == site.site_key
                assert keyed.intelligence == "high"

                # Registered site, no key -> refused.
                try:
                    await resolve_public_site(db, key=None, site=site.site_key, intelligence=None)
                    raise AssertionError("expected PublicAccessError")
                except PublicAccessError as exc:
                    assert exc.reason == "widget_key_required"

                # Reserved demo site -> open, client tier honoured.
                demo = await resolve_public_site(
                    db, key=None, site="hirebuddha", intelligence="basic",
                )
                assert not demo.tier_locked
                assert demo.site_key == "hirebuddha"
                assert demo.intelligence == "basic"
        finally:
            await engine.dispose()

    asyncio.run(run())
