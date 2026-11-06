"""
Returning-visitor memory, opt-in (M3-3): only when the site offers it and the
visitor opts in; conversations linked; the memory built from them; the agent
greets and knows them next time (text and voice); never shared between sites;
"forget me", erasure, retention and switching it off remove it; CORTEX
episodes follow the transcript window (WS8).
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings, site_entity_id
from app.main import app

PW = "supersecret1"


def _db(fn):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await fn(db)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _sql(q, p=None):
    async def go(db):
        res = await db.execute(text(q), p or {})
        await db.commit()
        try:
            return res.mappings().all()
        except Exception:
            return None
    return _db(go)


def _setup(client, *, memory=True):
    body = client.post("/auth/register", json={"email": f"mem_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": PW}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Memory Co"}, headers=h).json()
    priv = client.get(f"/tenant/websites/{site['id']}/privacy", headers=h).json()
    client.put(f"/tenant/websites/{site['id']}/privacy", headers=h,
               json={**priv, "consent_required": False, "memory_enabled": memory, "memory_days": 180})
    return h, site


def _post(client, path, body):
    return client.post(path, content=json.dumps(body), headers={"Content-Type": "text/plain"})


def _defaults(client, key, visitor):
    return _post(client, "/experiment/enroll", {"key": key, "visitor": visitor}).json()["defaults"]["memory"]


def _build():
    from app.memory import store as memory
    return _db(lambda db: memory.build_due(db, quiet_minutes=0))


def test_memory_needs_the_site_and_the_visitor():
    with TestClient(app) as client:
        h, site = _setup(client, memory=False)
        v = "visitor-" + uuid.uuid4().hex[:12]
        assert _defaults(client, site["public_key"], v)["offered"] is False
        assert _post(client, "/memory", {"key": site["public_key"], "visitor": v, "remember": True}).status_code == 409
        assert _post(client, "/memory", {"key": site["public_key"], "visitor": "x", "remember": True}).status_code == 422
        # A visitor who didn't opt in: their conversations aren't linked.
        r = client.post("/chat", json={"message": "What does it cost?", "key": site["public_key"], "visitor": v})
        assert r.status_code == 200
        assert _sql("SELECT visitor_id FROM conversations WHERE site_key = :s", {"s": site["site_key"]})[0][
            "visitor_id"] is None


def test_a_returning_visitor_is_welcomed_back_and_remembered():
    from app.transport.session_store import store as sessions

    with TestClient(app) as client:
        h, site = _setup(client)
        key, v = site["public_key"], "visitor-" + uuid.uuid4().hex[:12]
        d = _defaults(client, key, v)
        assert d == {"offered": True, "remembered": False, "welcome_back": None, "welcome_back_hi": None}
        assert _post(client, "/memory", {"key": key, "visitor": v, "remember": True}).json() == {"remembered": True}

        first = client.post("/chat", json={"message": "Do you support SSO with Okta?", "key": key, "visitor": v}).json()
        client.post("/chat", json={"message": "How much is the Growth plan?", "key": key, "visitor": v,
                                   "session_id": first["session_id"]})
        linked = _sql("SELECT visitor_id FROM conversations WHERE site_key = :s", {"s": site["site_key"]})
        assert linked and all(r["visitor_id"] == v for r in linked)
        assert _build() >= 1
        mem = _sql("SELECT topics, conversations, built_at FROM visitor_memories WHERE site_key = :s AND visitor_id = :v",
                   {"s": site["site_key"], "v": v})[0]
        assert any("SSO" in t for t in mem["topics"]) and mem["conversations"] == 1 and mem["built_at"]

        d = _defaults(client, key, v)
        assert d["remembered"] is True and d["welcome_back"].startswith("Welcome back! Last time you asked: \u201c")
        assert "Growth plan?" in d["welcome_back"] and "फिर से स्वागत है" in d["welcome_back_hi"]

        # Next visit: the agent has the notes at the start of its history.
        nxt = client.post("/chat", json={"message": "Hi again", "key": key, "visitor": v}).json()
        state = asyncio.run(sessions.load(nxt["session_id"], site_key=site["site_key"]))[1]
        assert state.visitor_id == v and state.memory_loaded
        assert "Notes from this visitor" in state.history[1].text and "SSO" in state.history[1].text

        # By voice: the spoken welcome is the welcome back.
        with client.websocket_connect(f"/ws/voice?key={key}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "hello", "payload": {"visitor": v, "tour": False}})
            spoken = None
            for _ in range(60):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "start" and env["payload"].get("text"):
                    spoken = env["payload"]["text"]
                    break
            assert spoken and spoken.startswith("Welcome back!")

        # Never across sites: the same visitor id elsewhere is a stranger.
        _, other = _setup(client)
        assert _defaults(client, other["public_key"], v)["remembered"] is False


def test_opting_in_mid_conversation_remembers_that_conversation():
    with TestClient(app) as client:
        h, site = _setup(client)
        key, v = site["public_key"], "visitor-" + uuid.uuid4().hex[:12]
        first = client.post("/chat", json={"message": "Do you integrate with Salesforce?", "key": key,
                                           "visitor": v}).json()
        assert _sql("SELECT visitor_id FROM conversations WHERE site_key = :s", {"s": site["site_key"]})[0][
            "visitor_id"] is None
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        client.post("/chat", json={"message": "And with HubSpot?", "key": key, "visitor": v,
                                   "session_id": first["session_id"]})
        assert _sql("SELECT visitor_id FROM conversations WHERE site_key = :s", {"s": site["site_key"]})[0][
            "visitor_id"] == v
        _build()
        topics = _sql("SELECT topics FROM visitor_memories WHERE site_key = :s", {"s": site["site_key"]})[0]["topics"]
        assert any("Salesforce" in t for t in topics), "the turns before the opt-in count too"

        # Over the socket, no voice welcome: the visitor id comes on the URL.
        with client.websocket_connect(f"/ws/voice?key={key}&visitor={v}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text", "payload": {"text": "Is there an API?"}})
            ends = 0
            for _ in range(300):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                    if ends >= 2:
                        break
            linked = None
            for _ in range(40):
                rows = _sql("SELECT channel, visitor_id FROM conversations WHERE site_key = :s",
                            {"s": site["site_key"]})
                linked = {r["channel"]: r["visitor_id"] for r in rows}.get("voice")
                if linked:
                    break
                time.sleep(0.1)
        assert linked == v


def test_forget_me_typed_or_by_the_button_and_erasure_and_retention():
    with TestClient(app) as client:
        h, site = _setup(client)
        key, v = site["public_key"], "visitor-" + uuid.uuid4().hex[:12]
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        client.post("/chat", json={"message": "Tell me about pricing", "key": key, "visitor": v})
        _build()

        r = client.post("/chat", json={"message": "Please forget me", "key": key, "visitor": v}).json()
        assert r["intent"] == "forget_me" and r["memory"] == "forgotten" and "forgotten" in r["text"]
        assert not _sql("SELECT 1 FROM visitor_memories WHERE site_key = :s", {"s": site["site_key"]})
        assert all(x["visitor_id"] is None for x in _sql(
            "SELECT visitor_id FROM conversations WHERE site_key = :s", {"s": site["site_key"]}))
        again = client.post("/chat", json={"message": "forget me", "key": key, "visitor": v}).json()
        assert "nothing to forget" in again["text"]

        # The widget's button.
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        assert _post(client, "/memory", {"key": key, "visitor": v, "remember": False}).json() == {
            "remembered": False, "forgotten": True}

        # Erasure by email reaches the memory through their conversation.
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        c = client.post("/chat", json={"message": "What integrations do you have?", "key": key, "visitor": v}).json()
        client.post("/leads", json={"key": key, "email": "returning@example.com", "session_id": c["session_id"]})
        erased = client.post(f"/tenant/websites/{site['id']}/privacy/erase", headers=h,
                             json={"email": "returning@example.com"}).json()
        assert erased["memories"] == 1

        # Retention: past memory_days since the last visit.
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        _sql("UPDATE visitor_memories SET last_seen_at = now() - interval '400 days' WHERE site_key = :s",
             {"s": site["site_key"]})
        from app.trust.retention import purge_expired
        removed = _db(purge_expired)
        assert removed["visitor_memories"] >= 1
        assert not _sql("SELECT 1 FROM visitor_memories WHERE site_key = :s", {"s": site["site_key"]})

        # Switching the feature off keeps nothing.
        _post(client, "/memory", {"key": key, "visitor": v, "remember": True})
        priv = client.get(f"/tenant/websites/{site['id']}/privacy", headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/privacy", headers=h, json={**priv, "memory_enabled": False})
        assert not _sql("SELECT 1 FROM visitor_memories WHERE site_key = :s", {"s": site["site_key"]})


def test_cortex_episodes_follow_the_transcript_window():
    with TestClient(app) as client:
        _, site = _setup(client)
        for q in ("What is your refund policy?", "Do you have an API?"):
            client.post("/chat", json={"message": f"{q} {uuid.uuid4().hex[:4]}", "key": site["public_key"]})
    eid = site_entity_id(site["site_key"])
    q = ("SELECT count(*) AS n FROM cortex_nodes n JOIN cortex_trees t ON t.id = n.tree_id "
         "WHERE t.memory_domain = 'episodic' AND t.entity_id = :e AND n.node_type = 'episode'")
    before = _sql(q, {"e": eid})[0]["n"]
    assert before >= 1, "the agent wrote episodes for these turns"
    _sql("UPDATE cortex_nodes n SET created_at = n.created_at - interval '400 days' FROM cortex_trees t "
         "WHERE t.id = n.tree_id AND t.entity_id = :e AND t.memory_domain = 'episodic'", {"e": eid})
    from app.trust.retention import purge_expired
    removed = _db(purge_expired)
    assert removed["cortex_episodes"] >= before
    assert _sql(q, {"e": eid})[0]["n"] == 0
