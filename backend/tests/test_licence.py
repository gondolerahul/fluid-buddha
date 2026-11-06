"""
Self-hosted licence (M3-5): verification offline (valid, expiring, grace,
expired, tampered, unknown key, malformed), the console's licence routes
(Owner installs; invalid and expired refused), and what an install does with
it: read-only console past the grace period while visitors keep working,
features outside the licence refused, websites and seats counted against it.
"""
from __future__ import annotations

import base64
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import get_settings
from app.licence import core, guard
from app.main import app

PW = "supersecret1"
KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw,
                                                     serialization.PublicFormat.Raw)).decode()
KEYS = {"test-1": PUB}


def token(*, days=365, sites=100000, seats=100000, features=None, grace=14, kid="test-1", issued_days_ago=1, key=KEY):
    now = int(time.time())
    return core.sign({"kid": kid, "lid": f"lic_{uuid.uuid4().hex[:8]}", "customer": "Acme Health",
                      "sites": sites, "seats": seats, "features": features or ["*"],
                      "iat": now - issued_days_ago * 86400, "exp": now + int(days * 86400), "grace_days": grace}, key)


def test_verification():
    lic = core.parse(token(days=200), KEYS)
    assert lic.customer == "Acme Health" and lic.has("campaigns") and lic.kid == "test-1"
    assert core.state(lic)["state"] == "valid"
    assert core.state(core.parse(token(days=10), KEYS))["state"] == "expiring"
    assert core.state(core.parse(token(days=-3), KEYS))["state"] == "grace"
    gone = core.state(core.parse(token(days=-30), KEYS))
    assert gone["state"] == "expired" and gone["usable"] is False
    assert core.state(None)["state"] == "missing"
    # Features listed, not "*".
    some = core.parse(token(features=["campaigns"]), KEYS)
    assert some.has("campaigns") and not some.has("byo_model")

    good = token()
    head, body, sig = good.split(".")
    payload = base64.urlsafe_b64decode(body + "==").replace(b'"sites":100000', b'"sites":999999')
    forged = ".".join([head, base64.urlsafe_b64encode(payload).rstrip(b"=").decode(), sig])
    for bad, reason in ((forged, "bad_signature"), (good[:-4] + "AAAA", "bad_signature"),
                        (token(key=Ed25519PrivateKey.generate()), "bad_signature"),
                        (token(kid="other"), "unknown_key"), ("FBL1.notjson.sig", "malformed"),
                        ("hello", "malformed"), ("", "malformed")):
        with pytest.raises(core.LicenceError) as e:
            core.parse(bad, KEYS)
        assert e.value.reason == reason, bad
    # Whitespace from copy-paste is fine.
    assert core.parse(good[:30] + "\n  " + good[30:], KEYS).customer == "Acme Health"


def test_the_built_in_key_verifies_its_own_licences():
    assert set(core.PUBLIC_KEYS) and all(len(base64.b64decode(v)) == 32 for v in core.PUBLIC_KEYS.values())


@contextmanager
def self_hosted(licence_key: str = ""):
    s = get_settings()
    before = (s.self_hosted, s.licence_key, dict(core.PUBLIC_KEYS))
    s.self_hosted, s.licence_key = True, licence_key
    core.PUBLIC_KEYS.clear()
    core.PUBLIC_KEYS.update(KEYS)
    guard._cache["at"] = 0.0
    _clear_installed()          # nothing left over from another run
    try:
        yield
    finally:
        s.self_hosted, s.licence_key = before[0], before[1]
        core.PUBLIC_KEYS.clear()
        core.PUBLIC_KEYS.update(before[2])
        guard._cache["at"] = 0.0
        _clear_installed()


def _clear_installed():
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                await db.execute(text("DELETE FROM install_licence"))
                await db.commit()
        finally:
            await engine.dispose()
    asyncio.run(run())


def _owner(client):
    body = client.post("/auth/register", json={"email": f"lic_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_not_enforced_on_the_hosted_service():
    with TestClient(app) as client:
        h = _owner(client)
        assert client.get("/tenant/licence", headers=h).json() == {"self_hosted": False}
        assert client.put("/tenant/licence", headers=h, json={"key": token()}).status_code == 409
        assert client.post("/tenant/websites", headers=h, json={"name": "Free"}).status_code == 201


def test_installing_a_licence_and_what_it_allows():
    with TestClient(app) as client:
        h = _owner(client)
        site = client.post("/tenant/websites", headers=h, json={"name": "Before"}).json()   # not yet self-hosted
        with self_hosted():
            st = client.get("/tenant/licence", headers=h).json()
            assert st["self_hosted"] is True and st["state"] == "missing" and st["usage"]["sites"] >= 1
            # No licence: reading works, changes don't (except installing one).
            assert client.get(f"/tenant/websites/{site['id']}", headers=h).status_code == 200
            refused = client.post("/tenant/websites", headers=h, json={"name": "Nope"})
            assert refused.status_code == 402 and "read-only" in refused.json()["detail"]
            # Visitors are never affected.
            assert client.post("/chat", json={"message": "hello", "key": site["public_key"]}).status_code == 200

            for bad, words in (("FBL1.notalicence.x", "isn't a FluidBuddha licence"),
                               (token(key=Ed25519PrivateKey.generate()), "changed or is incomplete"),
                               (token(days=-60), "expired")):
                r = client.put("/tenant/licence", headers=h, json={"key": bad})
                assert r.status_code == 422 and words in r.json()["detail"], r.text

            ok = client.put("/tenant/licence", headers=h, json={"key": token(days=200, features=["campaigns"])})
            assert ok.status_code == 200 and ok.json()["state"] == "valid" and ok.json()["source"] == "console"
            assert ok.json()["licence"]["features"] == ["campaigns"]
            assert client.post("/tenant/websites", headers=h, json={"name": "Now fine"}).status_code == 201
            # Outside the licence's features.
            r = client.get("/tenant/model-provider", headers=h)
            assert r.status_code == 402 and "byo_model" in r.json()["detail"]
            assert client.get(f"/tenant/websites/{site['id']}/campaigns", headers=h).status_code == 200

            # In grace: still works; the console says so.
            client.put("/tenant/licence", headers=h, json={"key": token(days=-2)})
            st = client.get("/tenant/licence", headers=h).json()
            assert st["state"] == "grace" and st["usable"] is True
            assert client.post("/tenant/websites", headers=h, json={"name": "Grace"}).status_code == 201


def test_expired_licence_from_the_environment_degrades_gracefully():
    with TestClient(app) as client:
        h = _owner(client)
        site = client.post("/tenant/websites", headers=h, json={"name": "Live site"}).json()
        with self_hosted(licence_key=token(days=-40)):
            st = client.get("/tenant/licence", headers=h).json()
            assert st["state"] == "expired" and st["source"] == "env"
            assert client.put(f"/tenant/websites/{site['id']}/profile", headers=h,
                              json={"agent_name": "Ava"}).status_code == 402
            assert client.get(f"/tenant/websites/{site['id']}/profile", headers=h).status_code == 200
            assert client.post("/chat", json={"message": "hi", "key": site["public_key"]}).status_code == 200
            # The way out: an Owner installs a renewal.
            assert client.put("/tenant/licence", headers=h, json={"key": token(days=365)}).json()["state"] == "valid"
            assert client.put(f"/tenant/websites/{site['id']}/profile", headers=h,
                              json={"agent_name": "Ava"}).status_code == 200


def test_sites_and_seats_are_counted_install_wide():
    with TestClient(app) as client:
        h = _owner(client)
        with self_hosted():
            from sqlalchemy import text
            import asyncio
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy.pool import NullPool

            async def counts():
                engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
                try:
                    async with AsyncSession(engine) as db:
                        s = (await db.execute(text("SELECT count(*) FROM tenant_websites"))).scalar()
                        u = (await db.execute(text(
                            "SELECT (SELECT count(DISTINCT user_id) FROM memberships) + (SELECT count(*) FROM invitations "
                            "WHERE accepted_at IS NULL AND expires_at > now())"))).scalar()
                        return s, u
                finally:
                    await engine.dispose()
            sites, seats = asyncio.run(counts())
            client.put("/tenant/licence", headers=h, json={"key": token(sites=sites + 1, seats=seats + 1)})
            assert client.post("/tenant/websites", headers=h, json={"name": "Last one"}).status_code == 201
            full = client.post("/tenant/websites", headers=h, json={"name": "One too many"})
            assert full.status_code == 402 and f"covers {sites + 1} websites" in full.json()["detail"]
            assert client.post("/tenant/team/invitations", headers=h,
                               json={"email": f"a_{uuid.uuid4().hex[:6]}@example.com", "role": "editor"}).status_code == 201
            r = client.post("/tenant/team/invitations", headers=h,
                            json={"email": f"b_{uuid.uuid4().hex[:6]}@example.com", "role": "editor"})
            assert r.status_code == 402 and "seats" in r.json()["detail"]


def test_only_an_owner_installs_a_licence():
    from app.auth import roles

    assert roles.required_role("PUT", "/tenant/licence") == "owner"
    assert roles.required_role("GET", "/tenant/licence") == "viewer"
