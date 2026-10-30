"""
Admin dashboard API tests (Phase 2+): tenant auth + website management.

    MOCK_AI=true python -m pytest tests/test_admin.py -q

Hits the live pgvector DB (tables are created lazily). Uses the FastAPI
TestClient so the full dependency graph (JWT bearer, current_tenant) is exercised.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.auth.security import hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("supersecret1")
    assert h != "supersecret1"
    assert verify_password("supersecret1", h)
    assert not verify_password("wrong", h)


def _auth(client: TestClient) -> tuple[dict, str]:
    email = f"t_{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def test_register_login_me_and_duplicate():
    from app.main import app

    with TestClient(app) as client:
        headers, email = _auth(client)
        # duplicate registration is rejected
        assert client.post("/auth/register",
                           json={"email": email, "password": "supersecret1"}).status_code == 409
        # login works, wrong password 401
        assert client.post("/auth/login",
                           json={"email": email, "password": "supersecret1"}).status_code == 200
        assert client.post("/auth/login",
                           json={"email": email, "password": "nope12345"}).status_code == 401
        # me requires a token
        assert client.get("/auth/me").status_code == 401
        assert client.get("/auth/me", headers=headers).json()["email"] == email


def test_website_crud_and_tenant_isolation():
    from app.main import app

    with TestClient(app) as client:
        h1, _ = _auth(client)
        created = client.post("/tenant/websites", json={
            "name": "Acme Store", "domain": "acme.test",
            "intelligence": "high", "design": "level2",
        }, headers=h1)
        assert created.status_code == 201, created.text
        wid = created.json()["id"]
        assert created.json()["site_key"]  # slug generated

        # invalid level rejected
        assert client.patch(f"/tenant/websites/{wid}", json={"intelligence": "bogus"},
                            headers=h1).status_code == 422
        # rename works
        assert client.patch(f"/tenant/websites/{wid}", json={"name": "Acme 2"},
                            headers=h1).json()["name"] == "Acme 2"

        # a different tenant cannot see or fetch it
        h2, _ = _auth(client)
        assert client.get(f"/tenant/websites/{wid}", headers=h2).status_code == 404
        assert all(w["id"] != wid for w in client.get("/tenant/websites", headers=h2).json())

        # delete
        assert client.delete(f"/tenant/websites/{wid}", headers=h1).status_code == 204
        assert client.get(f"/tenant/websites/{wid}", headers=h1).status_code == 404
