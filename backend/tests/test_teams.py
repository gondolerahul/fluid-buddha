"""
M2-1: people, roles, invitations, account switching and the audit log.

``test_every_tenant_route_checks_sign_in_and_role`` walks the whole API, so a
new route can't slip past the role table.
"""
from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import roles
from app.auth.security import create_access_token
from app.main import app

PW = "supersecret1"


def _email(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def _register(client: TestClient, email: str | None = None) -> tuple[dict, dict]:
    r = client.post("/auth/register", json={"email": email or _email("own"), "password": PW,
                                            "name": "Acme"})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def _join(client: TestClient, owner_h: dict, role: str) -> tuple[dict, dict]:
    """Invite a new person with ``role`` and accept as them."""
    email = _email(role)
    inv = client.post("/tenant/team/invitations", json={"email": email, "role": role},
                      headers=owner_h)
    assert inv.status_code == 201, inv.text
    token = inv.json()["link"].split("token=")[1]
    acc = client.post(f"/auth/invitations/{token}/accept", json={"password": PW, "name": role})
    assert acc.status_code == 200, acc.text
    return {"Authorization": f"Bearer {acc.json()['access_token']}"}, acc.json()


def _sql(sql: str, **params):
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings

    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                res = await conn.execute(text(sql), params)
                return res.mappings().all() if res.returns_rows else None
        finally:
            await engine.dispose()
    return asyncio.run(go())


# ---- the role table ---------------------------------------------------------------

def test_role_rules():
    assert roles.required_role("GET", "/tenant/websites/{website_id}/tour") == "viewer"
    assert roles.required_role("PUT", "/tenant/websites/{website_id}/tour") == "editor"
    assert roles.required_role("GET", "/tenant/websites/{website_id}/integrations") == "admin"
    assert roles.required_role("DELETE", "/tenant/websites/{website_id}") == "admin"
    assert roles.required_role("PATCH", "/tenant/websites/{website_id}") == "editor"
    assert roles.required_role("GET", "/tenant/billing") == "admin"
    assert roles.required_role("POST", "/tenant/billing/checkout") == "owner"
    assert roles.required_role("POST", "/tenant/team/invitations") == "admin"
    assert roles.required_role("GET", "/tenant/audit.csv") == "admin"
    assert roles.can_assign("owner", "owner") and not roles.can_assign("admin", "owner")
    assert roles.can_assign("admin", "editor") and not roles.can_assign("editor", "viewer")


def _below(role: str) -> str | None:
    i = roles.ROLES.index(role)
    return roles.ROLES[i - 1] if i else None


def test_every_tenant_route_checks_sign_in_and_role():
    with TestClient(app) as client:
        owner_h, _ = _register(client)
        tokens = {"owner": owner_h}
        for role in ("admin", "editor", "viewer"):
            tokens[role], _ = _join(client, owner_h, role)

        checked = 0
        for path, ops in app.openapi()["paths"].items():
            if not path.startswith("/tenant"):
                continue
            url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
            for method in ops:
                m = method.upper()
                r = client.request(m, url)
                assert r.status_code == 401, f"{m} {path} answers without sign-in ({r.status_code})"
                below = _below(roles.required_role(m, path))
                if below:
                    r = client.request(m, url, headers=tokens[below])
                    assert r.status_code == 403, f"{m} {path} lets a {below} in ({r.status_code})"
                checked += 1
        assert checked > 40


# ---- invitations and roles in practice -------------------------------------------

def test_invite_accept_and_what_each_role_can_do():
    with TestClient(app) as client:
        owner_h, owner = _register(client)
        site = client.post("/tenant/websites", json={"name": "Team Co"}, headers=owner_h).json()
        sid = site["id"]

        editor_h, editor = _join(client, owner_h, "editor")
        assert editor["role"] == "editor" and editor["tenant"]["id"] == owner["tenant"]["id"]
        me = client.get("/auth/me", headers=editor_h).json()
        assert me["role"] == "editor" and me["user"]["name"] == "editor"

        # An Editor works on the site but can't see billing, secrets or the team's controls.
        assert client.get(f"/tenant/websites/{sid}", headers=editor_h).status_code == 200
        assert client.put(f"/tenant/websites/{sid}/profile", headers=editor_h,
                          json={"agent_name": "Mira"}).status_code == 200
        assert client.get("/tenant/billing", headers=editor_h).status_code == 403
        assert client.get(f"/tenant/websites/{sid}/integrations", headers=editor_h).status_code == 403
        assert client.post("/tenant/team/invitations", headers=editor_h,
                           json={"email": _email(), "role": "viewer"}).status_code == 403
        assert client.delete(f"/tenant/websites/{sid}", headers=editor_h).status_code == 403
        team = client.get("/tenant/team", headers=editor_h).json()
        assert {m["role"] for m in team["members"]} == {"owner", "editor"}

        viewer_h, _ = _join(client, owner_h, "viewer")
        assert client.get(f"/tenant/websites/{sid}/tour", headers=viewer_h).status_code == 200
        assert client.put(f"/tenant/websites/{sid}/profile", headers=viewer_h,
                          json={"agent_name": "X"}).status_code == 403

        # Invitations: used once, revocable, not for someone already in.
        inv = client.post("/tenant/team/invitations", headers=owner_h,
                          json={"email": _email(), "role": "viewer"}).json()
        token = inv["link"].split("token=")[1]
        info = client.get(f"/auth/invitations/{token}").json()
        assert info["role"] == "viewer" and info["account"] == "Acme" and not info["has_user"]
        assert client.post(f"/auth/invitations/{token}/accept", json={}).status_code == 422
        assert client.delete(f"/tenant/team/invitations/{inv['id']}", headers=owner_h).status_code == 204
        assert client.get(f"/auth/invitations/{token}").status_code == 404
        assert client.post("/tenant/team/invitations", headers=owner_h,
                           json={"email": me["user"]["email"], "role": "viewer"}).status_code == 409
        assert client.post("/tenant/team/invitations", headers=owner_h,
                           json={"email": _email(), "role": "boss"}).status_code == 422

        # Removing someone takes effect at once, even with a still-valid token.
        assert client.delete(f"/tenant/team/members/{me['user']['id']}",
                             headers=owner_h).status_code == 204
        assert client.get(f"/tenant/websites/{sid}", headers=editor_h).status_code == 401


def test_owners_are_protected():
    with TestClient(app) as client:
        owner_h, owner = _register(client)
        owner_id = owner["user"]["id"]
        admin_h, admin = _join(client, owner_h, "admin")
        admin_id = admin["user"]["id"]

        # Only an Owner makes Owners; the last Owner can't be removed or demoted.
        assert client.post("/tenant/team/invitations", headers=admin_h,
                           json={"email": _email(), "role": "owner"}).status_code == 403
        assert client.patch(f"/tenant/team/members/{admin_id}", headers=admin_h,
                            json={"role": "owner"}).status_code == 403
        assert client.delete(f"/tenant/team/members/{owner_id}", headers=admin_h).status_code == 403
        assert client.patch(f"/tenant/team/members/{owner_id}", headers=owner_h,
                            json={"role": "admin"}).status_code == 409
        # Promote the Admin, then the first Owner may step down.
        assert client.patch(f"/tenant/team/members/{admin_id}", headers=owner_h,
                            json={"role": "owner"}).json()["role"] == "owner"
        assert client.patch(f"/tenant/team/members/{owner_id}", headers=owner_h,
                            json={"role": "admin"}).status_code == 200
        assert client.get("/tenant/billing", headers=owner_h).status_code == 200   # admin reads
        assert client.post("/tenant/billing/cancel", headers=owner_h).status_code == 403


def test_existing_person_joins_a_second_account_and_switches():
    with TestClient(app) as client:
        a_h, a = _register(client)
        b_h, b = _register(client)
        inv = client.post("/tenant/team/invitations", headers=a_h,
                          json={"email": b["user"]["email"], "role": "editor"}).json()
        token = inv["link"].split("token=")[1]
        assert client.get(f"/auth/invitations/{token}").json()["has_user"]
        # They must be signed in as themselves to accept.
        assert client.post(f"/auth/invitations/{token}/accept", json={}).status_code == 401
        assert client.post(f"/auth/invitations/{token}/accept", json={},
                           headers=a_h).status_code == 401
        joined = client.post(f"/auth/invitations/{token}/accept", json={}, headers=b_h).json()
        assert joined["tenant"]["id"] == a["tenant"]["id"] and joined["role"] == "editor"

        accounts = client.get("/auth/accounts", headers=b_h).json()
        assert {x["id"] for x in accounts} == {a["tenant"]["id"], b["tenant"]["id"]}
        sw = client.post("/auth/switch", json={"tenant_id": a["tenant"]["id"]}, headers=b_h).json()
        h2 = {"Authorization": f"Bearer {sw['access_token']}"}
        assert client.get("/auth/me", headers=h2).json()["id"] == a["tenant"]["id"]
        assert client.post("/auth/switch", json={"tenant_id": str(uuid.uuid4())},
                           headers=b_h).status_code == 404
        # Password sign-in lands in their own (first) account.
        login = client.post("/auth/login", json={"email": b["user"]["email"], "password": PW})
        assert login.json()["tenant"]["id"] == b["tenant"]["id"]


def test_tokens_without_an_account_id_still_work():
    """Tokens issued before teams named only the account; migrated Owners have
    the account id as their user id."""
    with TestClient(app) as client:
        _, owner = _register(client)
        legacy = create_access_token(uuid.UUID(owner["user"]["id"]))
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {legacy}"}).json()
        assert me["id"] == owner["tenant"]["id"] and me["role"] == "owner"


def test_require_sso_blocks_passwords_for_the_domain_but_not_the_owner():
    with TestClient(app) as client:
        domain = f"{uuid.uuid4().hex[:8]}.example"
        owner_h, owner = _register(client, email=f"boss@{domain}")
        email = f"dev@{domain}"
        inv = client.post("/tenant/team/invitations", headers=owner_h,
                          json={"email": email, "role": "editor"}).json()
        client.post(f"/auth/invitations/{inv['link'].split('token=')[1]}/accept",
                    json={"password": PW})
        tid = uuid.UUID(owner["tenant"]["id"])
        _sql("INSERT INTO tenant_sso (tenant_id, issuer, client_id, require_sso) "
             "VALUES (:t, 'https://idp.example', 'cid', true)", t=tid)
        _sql("INSERT INTO sso_domains (domain, tenant_id, token, verified_at) "
             "VALUES (:d, :t, 'tok', now())", t=tid, d=domain)
        r = client.post("/auth/login", json={"email": email, "password": PW})
        assert r.status_code == 403 and "single sign-on" in r.json()["detail"]
        assert client.post("/auth/login", json={"email": f"boss@{domain}",
                                                "password": PW}).status_code == 200


# ---- audit log ---------------------------------------------------------------------

def test_changes_and_sign_ins_are_in_the_audit_log():
    with TestClient(app) as client:
        owner_h, owner = _register(client)
        site = client.post("/tenant/websites", json={"name": "Audit Co"}, headers=owner_h).json()
        editor_h, editor = _join(client, owner_h, "editor")
        client.put(f"/tenant/websites/{site['id']}/profile", headers=editor_h,
                   json={"agent_name": "=HYPERLINK(\"x\")"})
        client.put(f"/tenant/websites/{site['id']}/profile", headers=editor_h,
                   json={"agent_name": 7})                       # 422: not a change
        assert client.put(f"/tenant/websites/{site['id']}/integrations", headers=editor_h,
                          json={}).status_code == 403            # refused: not a change
        client.post("/auth/login", json={"email": owner["user"]["email"], "password": "wrong-pass"})

        log = client.get("/tenant/audit", headers=owner_h).json()
        actions = [e["action"] for e in log]
        assert actions.count("update_profile") == 1
        put = next(e for e in log if e["action"] == "update_profile")
        assert put["actor_email"] == editor["user"]["email"]
        assert put["target_type"] == "website" and put["target_id"] == site["id"]
        assert put["details"]["role"] == "editor" and put["request_id"]
        for a in ("account.register", "create_website", "create_invitation",
                  "invitation.accept", "login.failed"):
            assert a in actions, a
        assert "put_integrations" not in actions
        assert [e["action"] for e in client.get("/tenant/audit", headers=owner_h,
                                                params={"action": "profile"}).json()] == ["update_profile"]

        assert client.get("/tenant/audit", headers=editor_h).status_code == 403
        csv_text = client.get("/tenant/audit.csv", headers=owner_h).text
        assert csv_text.startswith("time,who,action") and "update_profile" in csv_text

        # Another account sees none of it.
        other_h, _ = _register(client)
        assert [e["action"] for e in client.get("/tenant/audit", headers=other_h).json()] == [
            "account.register"]
