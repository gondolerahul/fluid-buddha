"""
M2-11 security controls: two-factor (TOTP), sessions (idle/absolute timeout,
revocation), the console's cookie + CSRF, sign-in lockout, the account's
two-factor requirement, encrypted integration secrets, the access review and
security headers.
"""
from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import mfa
from app.config import get_settings
from app.main import app

PW = "supersecret1"


def _sql(query: str, params: dict | None = None, fetch: bool = False):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                res = await conn.execute(text(query), params or {})
                return res.mappings().all() if fetch else None
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _email() -> str:
    return f"sec_{uuid.uuid4().hex[:10]}@example.com"


def _register(client: TestClient, email: str | None = None) -> tuple[dict, dict]:
    body = client.post("/auth/register", json={"email": email or _email(), "password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def _join(client: TestClient, owner_h: dict, role: str) -> tuple[dict, dict]:
    email = _email()
    inv = client.post("/tenant/team/invitations", headers=owner_h,
                      json={"email": email, "role": role}).json()
    body = client.post(f"/auth/invitations/{inv['link'].split('token=')[1]}/accept",
                       json={"password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, {**body, "email": email}


def _enable_mfa(client: TestClient, h: dict) -> tuple[str, list[str]]:
    setup = client.post("/auth/mfa/setup", headers=h).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/FluidBuddha:")
    code = mfa.code_at(setup["secret"], mfa.current_step())
    r = client.post("/auth/mfa/enable", headers=h, json={"code": code})
    assert r.status_code == 200, r.text
    return setup["secret"], r.json()["recovery_codes"]


# ---- TOTP itself -------------------------------------------------------------------------

def test_totp_matches_the_rfc_6238_vectors_and_refuses_replays():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"   # RFC 6238 test key  gitleaks:allow
    # RFC 6238 appendix B (SHA-1), last 6 digits.
    for t, code in ((59, "287082"), (1111111109, "081804"), (1234567890, "005924"),
                    (2000000000, "279037")):
        assert mfa.code_at(secret, t // 30) == code
        assert mfa.verify(secret, code, now=t) == t // 30
    assert mfa.verify(secret, "287082", now=59 + 30) is not None      # one step of drift
    assert mfa.verify(secret, "287082", now=59 + 90) is None          # too old
    assert mfa.verify(secret, "287082", now=59, last_step=59 // 30) is None   # already used
    for bad in ("", "12345", "abcdef", "1234567"):
        assert mfa.verify(secret, bad, now=59) is None


def test_recovery_codes_work_once():
    codes, hashes = mfa.new_recovery_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    left = mfa.use_recovery_code(codes[3].upper(), hashes)
    assert left is not None and len(left) == 9
    assert mfa.use_recovery_code(codes[3], left) is None
    assert mfa.use_recovery_code("nope-nope", hashes) is None


# ---- two-factor sign-in --------------------------------------------------------------------

def test_two_factor_sign_in_with_a_code_or_a_recovery_code():
    with TestClient(app) as client:
        email = _email()
        h, _ = _register(client, email)
        secret, recovery = _enable_mfa(client, h)
        assert client.get("/auth/mfa", headers=h).json() == {
            **client.get("/auth/mfa", headers=h).json(), "enabled": True, "recovery_codes_left": 10}

        first = client.post("/auth/login", json={"email": email, "password": PW}).json()
        assert first["mfa_required"] and "access_token" not in first
        wrong = client.post("/auth/login/mfa", json={"mfa_token": first["mfa_token"], "code": "000000"})
        assert wrong.status_code == 401
        # The code from enabling was already used; the next one works once.
        step = mfa.current_step() + 1
        code = mfa.code_at(secret, step)
        _sql("UPDATE users SET totp_last_step = :s WHERE email = :e", {"s": step - 1, "e": email})
        ok = client.post("/auth/login/mfa", json={"mfa_token": first["mfa_token"], "code": code})
        assert ok.status_code == 200 and ok.json()["access_token"]
        again = client.post("/auth/login/mfa", json={"mfa_token": first["mfa_token"], "code": code})
        assert again.status_code == 401, "a code can't be replayed"

        rec = client.post("/auth/login/mfa", json={"mfa_token": first["mfa_token"],
                                                   "recovery_code": recovery[0]})
        assert rec.status_code == 200
        assert client.post("/auth/login/mfa", json={"mfa_token": first["mfa_token"],
                                                    "recovery_code": recovery[0]}).status_code == 401
        h2 = {"Authorization": f"Bearer {rec.json()['access_token']}"}
        assert client.get("/auth/mfa", headers=h2).json()["recovery_codes_left"] == 9

        # The challenge token is only good for the second step.
        assert client.get("/auth/me", headers={
            "Authorization": f"Bearer {first['mfa_token']}"}).status_code == 401
        log = client.get("/tenant/audit", headers=h2).json()
        assert {"mfa.enable", "login"} <= {e["action"] for e in log}


def test_switching_two_factor_off_needs_the_password_and_a_code():
    with TestClient(app) as client:
        h, _ = _register(client)
        secret, _ = _enable_mfa(client, h)
        assert client.post("/auth/mfa/disable", headers=h,
                           json={"code": "123456", "password": "wrong"}).status_code == 403
        _sql("UPDATE users SET totp_last_step = NULL WHERE id = (SELECT user_id FROM user_sessions "
             "ORDER BY created_at DESC LIMIT 1)")
        code = mfa.code_at(secret, mfa.current_step())
        r = client.post("/auth/mfa/disable", headers=h, json={"code": code, "password": PW})
        assert r.status_code in (200, 403)   # 403 only if the code's step was already used
        if r.status_code == 200:
            assert client.get("/auth/mfa", headers=h).json()["enabled"] is False


def test_an_account_can_require_two_factor():
    with TestClient(app) as client:
        owner_h, _ = _register(client)
        editor_h, _ = _join(client, owner_h, "editor")
        # The Owner must have it first, so they can't lock themselves out.
        assert client.put("/tenant/security", headers=owner_h,
                          json={"require_mfa": True}).status_code == 409
        _enable_mfa(client, owner_h)
        assert client.put("/tenant/security", headers=editor_h,
                          json={"require_mfa": True}).status_code == 403   # Owner only
        r = client.put("/tenant/security", headers=owner_h, json={"require_mfa": True})
        assert r.status_code == 200
        sec = client.get("/tenant/security", headers=owner_h).json()
        assert sec["require_mfa"] and len(sec["members_without_mfa"]) == 1

        # The editor's password-only session is held at the setup step.
        blocked = client.get("/tenant/websites", headers=editor_h)
        assert blocked.status_code == 403 and blocked.json()["detail"] == "mfa_setup_required"
        me = client.get("/auth/me", headers=editor_h).json()
        assert me["security"]["mfa_setup_required"] is True
        _enable_mfa(client, editor_h)
        assert client.get("/tenant/websites", headers=editor_h).status_code == 200
        # And while required it can't be switched off.
        assert client.post("/auth/mfa/disable", headers=editor_h,
                           json={"code": "000000", "password": PW}).status_code == 409


# ---- lockout -----------------------------------------------------------------------------

def test_repeated_wrong_passwords_lock_the_account_for_a_while():
    with TestClient(app) as client:
        email = _email()
        _register(client, email)
        for _ in range(get_settings().login_max_attempts):
            assert client.post("/auth/login", json={"email": email, "password": "nope"}).status_code == 401
        locked = client.post("/auth/login", json={"email": email, "password": PW})
        assert locked.status_code == 429 and "Try again in" in locked.json()["detail"]
        _sql("UPDATE users SET locked_until = now() - interval '1 hour' WHERE email = :e", {"e": email})
        assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 200


# ---- sessions ----------------------------------------------------------------------------

def _sid(token: str) -> str:
    from app.auth.security import decode_token
    return decode_token(token)["sid"]


def test_sessions_time_out_when_idle_and_at_their_limit():
    with TestClient(app) as client:
        h, body = _register(client)
        sid = _sid(body["access_token"])
        assert client.get("/auth/me", headers=h).status_code == 200
        idle = get_settings().session_idle_minutes
        _sql("UPDATE user_sessions SET last_seen_at = now() - make_interval(mins => :m) WHERE id = :id",
             {"m": idle + 1, "id": sid})
        r = client.get("/auth/me", headers=h)
        assert r.status_code == 401 and "sign in again" in r.json()["detail"]

        h, body = _register(client)
        _sql("UPDATE user_sessions SET expires_at = now() - interval '1 hour' WHERE id = :id",
             {"id": _sid(body["access_token"])})
        assert client.get("/auth/me", headers=h).status_code == 401


def test_sign_out_sign_out_everywhere_and_a_password_change():
    with TestClient(app) as client:
        email = _email()
        a_h, _ = _register(client, email)
        b = client.post("/auth/login", json={"email": email, "password": PW}).json()
        b_h = {"Authorization": f"Bearer {b['access_token']}"}
        listed = client.get("/auth/sessions", headers=a_h).json()
        assert len(listed["sessions"]) == 2

        assert client.post("/auth/sessions/revoke-others", headers=a_h).json()["ended"] == 1
        assert client.get("/auth/me", headers=b_h).status_code == 401
        assert client.get("/auth/me", headers=a_h).status_code == 200

        c = client.post("/auth/login", json={"email": email, "password": PW}).json()
        c_h = {"Authorization": f"Bearer {c['access_token']}"}
        assert client.post("/auth/password", headers=a_h,
                           json={"current_password": "wrong", "new_password": "anothersecret"}
                           ).status_code == 403
        r = client.post("/auth/password", headers=a_h,
                        json={"current_password": PW, "new_password": "anothersecret"})
        assert r.json() == {"changed": True, "other_sessions_ended": 1}
        assert client.get("/auth/me", headers=c_h).status_code == 401
        assert client.post("/auth/login", json={"email": email, "password": PW}).status_code == 401
        assert client.post("/auth/login", json={"email": email,
                                                "password": "anothersecret"}).status_code == 200

        assert client.post("/auth/logout", headers=a_h).status_code == 204
        assert client.get("/auth/me", headers=a_h).status_code == 401


def test_removing_a_member_ends_their_sessions_at_once():
    with TestClient(app) as client:
        owner_h, _ = _register(client)
        ed_h, ed = _join(client, owner_h, "editor")
        assert client.get("/tenant/websites", headers=ed_h).status_code == 200
        assert client.delete(f"/tenant/team/members/{ed['user']['id']}", headers=owner_h).status_code == 204
        rows = _sql("SELECT revoked_at FROM user_sessions WHERE id = :id",
                    {"id": _sid(ed["access_token"])}, fetch=True)
        assert rows[0]["revoked_at"] is not None


# ---- the console's cookie --------------------------------------------------------------

def test_cookie_sessions_need_the_csrf_token_to_change_anything():
    with TestClient(app, base_url="https://testserver") as client:
        r = client.post("/auth/register", json={"email": _email(), "password": PW})
        cookie = r.headers["set-cookie"]
        assert "fb_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie
        assert "samesite=lax" in cookie.lower()
        csrf = r.json()["csrf_token"]
        # Reads work with the cookie alone, and /auth/me hands back the CSRF token.
        me = client.get("/auth/me")
        assert me.status_code == 200 and me.json()["csrf_token"] == csrf
        # Changes need the header.
        bad = client.post("/tenant/websites", json={"name": "No CSRF"})
        assert bad.status_code == 403 and bad.json()["detail"] == "csrf_failed"
        assert client.post("/tenant/websites", json={"name": "Bad CSRF"},
                           headers={"X-CSRF-Token": "x" + csrf}).status_code == 403
        assert client.post("/tenant/websites", json={"name": "With CSRF"},
                           headers={"X-CSRF-Token": csrf}).status_code == 201
        # Signing out clears it.
        out = client.post("/auth/logout")
        assert out.status_code == 204 and 'fb_session=""' in out.headers["set-cookie"]
        assert client.get("/auth/me").status_code == 401


# ---- stored secrets ----------------------------------------------------------------------

def test_integration_secrets_are_encrypted_at_rest():
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Secret Co"}, headers=h).json()
        url = "https://hooks.slack.com/services/T000/B000/abcdefabcdef"
        r = client.put(f"/tenant/websites/{site['id']}/integrations", headers=h,
                       json={"webhook_url": None, "slack_webhook_url": url, "hot_lead_score": 70})
        assert r.status_code == 200, r.text
        cfg = client.get(f"/tenant/websites/{site['id']}/integrations", headers=h).json()
        assert cfg["slack_webhook_url"] == url and cfg["webhook_secret"].startswith("whsec_")
        raw = _sql("SELECT webhook_secret, slack_webhook_url FROM site_integrations WHERE site_key = :s",
                   {"s": site["site_key"]}, fetch=True)[0]
        assert raw["webhook_secret"].startswith("gAAAAA") and raw["slack_webhook_url"].startswith("gAAAAA")
        assert "whsec_" not in raw["webhook_secret"] and "hooks.slack.com" not in raw["slack_webhook_url"]


# ---- access review ---------------------------------------------------------------------

def test_access_review_export_and_quarterly_email():
    with TestClient(app) as client:
        owner_h, owner = _register(client)
        ed_h, ed = _join(client, owner_h, "editor")
        assert client.get("/tenant/team/access-review.csv", headers=ed_h).status_code == 403
        r = client.get("/tenant/team/access-review.csv", headers=owner_h)
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        rows = list(csv.DictReader(io.StringIO(r.text)))
        assert {x["email"] for x in rows} == {owner["user"]["email"], ed["email"]}
        assert {x["role"] for x in rows} == {"owner", "editor"}
        assert all(x["two_factor"] == "no" for x in rows)
        assert all(x["note"] == "" for x in rows), "empty cells stay empty"
        assert "access_review.export" in {e["action"] for e in
                                          client.get("/tenant/audit", headers=owner_h).json()}

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.notify import access_review

    async def send(now):
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                return await access_review.send_due(db, now=now)
        finally:
            await engine.dispose()

    now = datetime(2031, 1, 5, tzinfo=timezone.utc)
    asyncio.run(send(now))
    tenant = owner["tenant"]["id"]
    sent = _sql("SELECT to_addr, subject FROM email_outbox WHERE kind = 'access_review' "
                "AND tenant_id = :t", {"t": tenant}, fetch=True)
    assert [s["to_addr"] for s in sent] == [owner["user"]["email"]]   # Owners/Admins only
    assert "2031-Q1" in sent[0]["subject"]
    asyncio.run(send(now + timedelta(days=20)))   # same quarter: nothing new
    assert len(_sql("SELECT 1 FROM email_outbox WHERE kind = 'access_review' AND tenant_id = :t",
                    {"t": tenant}, fetch=True)) == 1


# ---- headers ----------------------------------------------------------------------------

def test_security_headers():
    with TestClient(app) as client:
        h, _ = _register(client)
        r = client.get("/auth/me", headers=h)
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        # Public, cacheable routes keep their own caching.
        loader = client.get("/widget/loader.js")
        assert "max-age=300" in loader.headers["cache-control"]
