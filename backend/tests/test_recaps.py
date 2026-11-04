"""
Shareable recap pages (M2-6): built from the transcript, behind a secret link,
branded and safe to render, views and forwards counted toward the lead, and
gone with expiry, erasure or a revoke.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.recaps.store import rule_summary

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


def _run(fn):
    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await fn(db)
        finally:
            await engine.dispose()
    return asyncio.run(go())


def _tenant(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"rc_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_rule_summary():
    turns = [{"question": q} for q in ("What does it cost?", "Do you integrate with HubSpot?",
                                       "Is there a trial?", "Who uses it?", "How long is setup?")]
    s = rule_summary(turns)
    assert s.startswith("You asked 5 questions: What does it cost; Do you integrate with HubSpot")
    assert s.endswith("and 1 more.") and rule_summary([]) == ""


def test_recap_link_page_views_and_lead():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Recap Co", "domain": "recap.example"},
                           headers=h).json()
        wid, key = site["id"], site["public_key"]
        base = f"/tenant/websites/{wid}"
        assert client.put(f"{base}/profile", json={"cta_url": "javascript:alert(1)"}, headers=h).status_code == 422
        client.put(f"{base}/profile", json={"company_name": "Recap Co", "cta_label": "Book a demo",
                                            "cta_url": "https://recap.example/demo"}, headers=h)

        # Nothing asked yet: nothing to recap.
        assert client.post("/recap", json={"key": key, "session_id": "nope"}).status_code == 404

        sid = None
        for msg in ("show me the roi for my team " + uuid.uuid4().hex[:6],
                    "Is it safe? </script><script>alert(1)</script>"):
            sid = client.post("/chat", json={"message": msg, "key": key, "session_id": sid,
                                             "page": "/pricing"}).json()["session_id"]
        made = client.post("/recap", json={"key": key, "session_id": sid}, headers=UA)
        assert made.status_code == 200, made.text
        url = made.json()["url"]
        token = url.split("/r/")[1]
        assert url.startswith(get_settings().public_api_url) and len(token) >= 40
        assert made.json()["emailed"] is False

        page = client.get(f"/r/{token}", headers=UA)
        assert page.status_code == 200
        html = page.text
        assert "Your conversation with" in html and "show me the roi for my team" in html
        assert "You asked 2 questions" in html                     # mock mode: the plain summary
        assert 'href="https://recap.example/demo"' in html and "Book a demo" in html
        assert 'href="https://recap.example/pricing"' in html      # back to where they were
        assert '"component_type":"roi_calculator"' in html          # drawn by the recap bundle
        assert "fluid-buddha-recap.global.js" in html
        assert "<script>alert(1)" not in html and "&lt;/script&gt;&lt;script&gt;alert(1)" in html
        csp = page.headers["content-security-policy"]
        assert "script-src http://localhost:4000;" in csp and "default-src 'none'" in csp
        assert page.headers["referrer-policy"] == "no-referrer" and "noindex" in page.headers["x-robots-tag"]
        assert "fb_rv" in page.cookies or client.cookies.get("fb_rv")

        client.get(f"/r/{token}", headers=UA)                      # same person again
        client.get(f"/r/{token}", headers={"User-Agent": "Slackbot-LinkExpanding 1.0"})   # not counted
        listed = client.get(f"{base}/recaps", headers=h).json()["recaps"]
        assert (listed[0]["views"], listed[0]["viewers"], listed[0]["forwards"]) == (2, 1, 0)
        assert listed[0]["url"] == url

        # Asking again with an email: same link, refreshed, emailed, and a lead.
        sid = client.post("/chat", json={"message": "Is there a free trial?", "key": key,
                                         "session_id": sid}).json()["session_id"]
        again = client.post("/recap", json={"key": key, "session_id": sid, "email": "ana@buyer.example"},
                            headers=UA).json()
        assert again["url"] == url and again["emailed"] is True
        assert "Is there a free trial?" in client.get(f"/r/{token}", headers=UA).text
        assert client.post("/recap", json={"key": key, "session_id": sid, "email": "not-an-email"}).status_code == 422
        lead = next(x for x in client.get(f"{base}/leads", headers=h).json()["items"]
                    if x["email"] == "ana@buyer.example")
        assert lead["source"] == "recap" and lead["recap"]["views"] == 3
        score_before = lead["score"]

        # Forwarded: a new person opens it.
        client.cookies.clear()
        client.get(f"/r/{token}", headers=UA)
        lead = next(x for x in client.get(f"{base}/leads", headers=h).json()["items"]
                    if x["email"] == "ana@buyer.example")
        assert lead["recap"]["forwards"] == 1 and lead["score"] == min(100, score_before + 10)

        # Unknown, malformed and expired links all look the same.
        for bad in ("x" * 43, "short", "has spaces%20in-it-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"):
            r = client.get(f"/r/{bad}")
            assert r.status_code == 404 and "isn't available" in r.text

        async def expire(db):
            await db.execute(text("UPDATE recaps SET expires_at = now() - interval '1 minute' WHERE token = :t"),
                             {"t": token})
            await db.commit()
        _run(expire)
        assert client.get(f"/r/{token}").status_code == 404
        # Asking again gives it a fresh expiry.
        assert client.post("/recap", json={"key": key, "session_id": sid}).json()["url"] == url
        assert client.get(f"/r/{token}", headers=UA).status_code == 200

        # Another tenant can't see or revoke it.
        h2 = _tenant(client)
        assert client.get(f"{base}/recaps", headers=h2).status_code == 404

        # Erasing the visitor removes the conversation, and the recap with it.
        client.post(f"{base}/privacy/erase", json={"email": "ana@buyer.example"}, headers=h)
        assert client.get(f"/r/{token}").status_code == 404
        assert client.get(f"{base}/recaps", headers=h).json()["recaps"] == []


def test_revoke_and_expiry_setting():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Revoke Co"}, headers=h).json()
        base = f"/tenant/websites/{site['id']}"
        priv = client.get(f"{base}/privacy", headers=h).json()
        assert priv["recap_days"] == 90
        assert client.put(f"{base}/privacy", json={**priv, "recap_days": 3}, headers=h).status_code == 422
        client.put(f"{base}/privacy", json={**priv, "recap_days": 7}, headers=h)

        sid = client.post("/chat", json={"message": "What do you do?", "key": site["public_key"]}).json()["session_id"]
        made = client.post("/recap", json={"key": site["public_key"], "session_id": sid}).json()
        from datetime import datetime, timezone
        days = (datetime.fromisoformat(made["expires_at"]) - datetime.now(timezone.utc)).days
        assert 6 <= days <= 7
        rid = client.get(f"{base}/recaps", headers=h).json()["recaps"][0]["id"]
        assert client.delete(f"{base}/recaps/{rid}", headers=h).status_code == 204
        assert client.get(f"/r/{made['url'].split('/r/')[1]}").status_code == 404
        assert client.delete(f"{base}/recaps/{rid}", headers=h).status_code == 404
