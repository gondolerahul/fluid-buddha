"""
M2-1 single sign-on, against a fake OpenID Connect provider: real RSA-signed
ID tokens, PKCE checked by the fake, DNS-over-HTTPS for domain proof.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import sso
from app.config import get_settings
from app.main import app

from tests.test_teams import PW, _register, _sql

ISSUER = "https://idp.test"
CLIENT_ID = "fb-client"
SECRET = "s3cret-value"


class FakeIdP:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        self.jwks = {"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]}
        self.txt: dict[str, list[str]] = {}
        self.pending: dict[str, dict] = {}   # code -> {nonce, challenge, email, ...}
        self.claims_override: dict = {}

    def authorize(self, url: str, email: str, **extra) -> str:
        """What the user's browser does at the IdP: returns the code."""
        q = parse_qs(urlsplit(url).query)
        assert q["client_id"] == [CLIENT_ID] and q["code_challenge_method"] == ["S256"]
        code = uuid.uuid4().hex
        self.pending[code] = {"nonce": q["nonce"][0], "challenge": q["code_challenge"][0],
                              "email": email, **extra}
        return code

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"{ISSUER}/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token", "jwks_uri": f"{ISSUER}/keys"})
        if url == f"{ISSUER}/keys":
            return httpx.Response(200, json=self.jwks)
        if url == f"{ISSUER}/token":
            form = parse_qs(request.content.decode())
            p = self.pending.pop(form["code"][0], None)
            if p is None or form["client_secret"] != [SECRET]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(form["code_verifier"][0].encode()).digest()).rstrip(b"=").decode()
            if challenge != p["challenge"]:
                return httpx.Response(400, json={"error": "invalid_grant",
                                                 "error_description": "PKCE mismatch"})
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": CLIENT_ID, "sub": p["email"], "email": p["email"],
                      "email_verified": True, "nonce": p["nonce"], "iat": now,
                      "exp": now + 300, "name": "Sam SSO", **self.claims_override}
            token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "k1"})
            return httpx.Response(200, json={"id_token": token, "access_token": "x"})
        if url.startswith(get_settings().dns_over_https_url):
            name = request.url.params["name"]
            return httpx.Response(200, json={"Answer": [
                {"name": name, "type": 16, "data": f'"{v}"'} for v in self.txt.get(name, [])]})
        return httpx.Response(404)


@pytest.fixture
def idp(monkeypatch):
    fake = FakeIdP()
    monkeypatch.setattr(sso, "_transport", httpx.MockTransport(fake.handler))
    sso._discovery_cache.clear()
    return fake


def _setup_account(client, idp, domain, default_role="editor"):
    owner_h, owner = _register(client, email=f"boss@{domain}")
    cfg = client.put("/tenant/sso", headers=owner_h, json={
        "issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": SECRET,
        "default_role": default_role})
    assert cfg.status_code == 200, cfg.text
    d = client.post("/tenant/sso/domains", headers=owner_h, json={"domain": domain}).json()
    idp.txt[domain] = [d["txt_value"]]
    assert client.post(f"/tenant/sso/domains/{domain}/verify", headers=owner_h).json()["verified"]
    return owner_h, owner


def _callback(client, url, code):
    state = parse_qs(urlsplit(url).query)["state"][0]
    return client.get("/auth/sso/callback", params={"state": state, "code": code},
                      follow_redirects=False)


def _token_from(resp) -> str:
    """The session the callback started: the console lands on /sso (no token in
    the address) with an httpOnly session cookie (M2-11)."""
    loc = resp.headers["location"]
    assert loc.endswith("/sso") and "token" not in loc, loc
    cookie = resp.headers["set-cookie"]
    assert "fb_session=" in cookie and "HttpOnly" in cookie, cookie
    return cookie.split("fb_session=")[1].split(";")[0]


def test_domain_must_be_proven_before_it_signs_anyone_in(idp):
    with TestClient(app) as client:
        domain = f"{uuid.uuid4().hex[:8]}.example"
        owner_h, _ = _register(client)
        assert client.put("/tenant/sso", headers=owner_h, json={
            "issuer": "https://nowhere.test", "client_id": "x"}).status_code == 422
        client.put("/tenant/sso", headers=owner_h, json={
            "issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": SECRET})
        assert client.post("/tenant/sso/domains", headers=owner_h,
                           json={"domain": "not a domain"}).status_code == 422
        d = client.post("/tenant/sso/domains", headers=owner_h, json={"domain": domain}).json()
        assert d["txt_value"].startswith("fluidbuddha-verify=") and not d["verified"]
        # Not proven yet: no sign-in for that domain, and verify says so.
        assert client.post("/auth/sso/start", json={"email": f"a@{domain}"}).status_code == 400
        assert client.post(f"/tenant/sso/domains/{domain}/verify", headers=owner_h).status_code == 409
        idp.txt[domain] = ["v=spf1 -all", d["txt_value"]]
        assert client.post(f"/tenant/sso/domains/{domain}/verify", headers=owner_h).status_code == 200
        # Another account can't take a proven domain.
        other_h, _ = _register(client)
        assert client.post("/tenant/sso/domains", headers=other_h,
                           json={"domain": domain}).status_code == 409
        # The secret is stored encrypted and never returned.
        cfg = client.get("/tenant/sso", headers=owner_h).json()
        assert cfg["has_secret"] and "client_secret" not in cfg and cfg["domains"][0]["verified"]
        rows = _sql("SELECT client_secret_enc FROM tenant_sso WHERE client_id = :c", c=CLIENT_ID)
        assert all(SECRET not in r["client_secret_enc"] for r in rows)


def test_company_sso_signs_in_and_creates_members(idp):
    with TestClient(app) as client:
        domain = f"{uuid.uuid4().hex[:8]}.example"
        owner_h, owner = _setup_account(client, idp, domain)
        email = f"sam@{domain}"
        url = client.post("/auth/sso/start", json={"email": email}).json()["url"]
        assert url.startswith(f"{ISSUER}/authorize?") and "login_hint" in url
        resp = _callback(client, url, idp.authorize(url, email))
        assert resp.status_code == 303
        h = {"Authorization": f"Bearer {_token_from(resp)}"}
        me = client.get("/auth/me", headers=h).json()
        assert me["id"] == owner["tenant"]["id"] and me["role"] == "editor"
        assert me["user"]["email"] == email and me["user"]["name"] == "Sam SSO"
        # They have no password; signing in again keeps the same role.
        assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 401
        url = client.post("/auth/sso/start", json={"email": email}).json()["url"]
        assert _callback(client, url, idp.authorize(url, email)).status_code == 303
        team = client.get("/tenant/team", headers=owner_h).json()
        assert [m["role"] for m in team["members"] if m["email"] == email] == ["editor"]
        log = client.get("/tenant/audit", headers=owner_h, params={"action": "login"}).json()
        assert any(e["details"].get("method") == "sso:oidc" for e in log)


def test_tampered_or_replayed_sign_ins_are_refused(idp):
    with TestClient(app) as client:
        domain = f"{uuid.uuid4().hex[:8]}.example"
        _setup_account(client, idp, domain)
        email = f"eve@{domain}"

        def attempt(**override):
            idp.claims_override = override
            url = client.post("/auth/sso/start", json={"email": email}).json()["url"]
            r = _callback(client, url, idp.authorize(url, email))
            idp.claims_override = {}
            return r

        for override in ({"nonce": "other"}, {"aud": "someone-else"}, {"iss": "https://evil.test"},
                         {"email_verified": False}, {"exp": int(time.time()) - 3600},
                         {"email": f"eve@not-{domain}"}):
            r = attempt(**override)
            assert "sso_error=" in r.headers["location"], override

        # A state works once.
        url = client.post("/auth/sso/start", json={"email": email}).json()["url"]
        code = idp.authorize(url, email)
        assert _token_from(_callback(client, url, code))
        assert "sso_error=" in _callback(client, url, idp.authorize(url, email)).headers["location"]
        # A token signed by another key.
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        idp.key, real = other, idp.key
        r = _callback(client, *(lambda u: (u, idp.authorize(u, email)))(
            client.post("/auth/sso/start", json={"email": email}).json()["url"]))
        idp.key = real
        assert "sso_error=" in r.headers["location"]
        # The provider's own error.
        r = client.get("/auth/sso/callback", params={"error": "access_denied",
                                                     "error_description": "User cancelled"},
                       follow_redirects=False)
        assert "User%20cancelled" in r.headers["location"]


def test_google_only_signs_in_existing_members(idp, monkeypatch):
    with TestClient(app) as client:
        assert client.post("/auth/sso/start", json={"provider": "google"}).status_code == 400
        s = get_settings()
        s.google_client_id, s.google_client_secret = CLIENT_ID, SECRET
        monkeypatch.setattr(sso, "GOOGLE_ISSUER", ISSUER)
        _, owner = _register(client)
        url = client.post("/auth/sso/start", json={"provider": "google"}).json()["url"]
        resp = _callback(client, url, idp.authorize(url, owner["user"]["email"]))
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {_token_from(resp)}"}).json()
        assert me["id"] == owner["tenant"]["id"] and me["role"] == "owner"
        # A Google address with no account: told to get an invitation.
        url = client.post("/auth/sso/start", json={"provider": "google"}).json()["url"]
        r = _callback(client, url, idp.authorize(url, f"stranger-{uuid.uuid4().hex[:6]}@gmail.com"))
        assert "invitation" in r.headers["location"]


def test_sso_settings_need_the_owner(idp):
    with TestClient(app) as client:
        owner_h, _ = _register(client)
        from tests.test_teams import _join
        admin_h, _ = _join(client, owner_h, "admin")
        assert client.get("/tenant/sso", headers=admin_h).json()["configured"] is False
        assert client.put("/tenant/sso", headers=admin_h, json={
            "issuer": ISSUER, "client_id": CLIENT_ID}).status_code == 403
        assert client.post("/tenant/sso/domains", headers=admin_h,
                           json={"domain": "x.example"}).status_code == 403
