"""
M2-2 live takeover: an operator sees who's on the site, takes a voice or text
conversation over from the agent, chats, rings the visitor (WebRTC
signalling), and hands back — with the agent learning what was said.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.live.turn import ice_servers
from app.main import app

from tests.test_teams import _join, _register


def _site(client):
    owner_h, owner = _register(client)
    site = client.post("/tenant/websites", json={"name": "Live Co"}, headers=owner_h).json()
    return owner_h, owner, site


def _until(ws, pred, limit=400):
    """Receive JSON frames until one matches ``pred``; return it."""
    for _ in range(limit):
        env = ws.receive_json()
        if pred(env):
            return env
    raise AssertionError("expected frame never arrived")


def _is(channel, type_):
    return lambda e: e.get("channel") == channel and e.get("type") == type_


def _op(type_, session_id=None):
    return lambda e: e.get("type") == type_ and (session_id is None or e.get("session_id") == session_id)


def _drain_turn(ws):
    """Wait for the agent's answer to finish (ack + answer audio)."""
    ends = 0
    for _ in range(400):
        env = ws.receive_json()
        if env["channel"] == "AUDIO" and env["type"] == "end":
            ends += 1
            if ends >= 2:
                return


def test_relay_credentials_follow_the_coturn_shared_secret_scheme():
    s = get_settings()
    s.turn_urls, s.turn_secret, s.turn_ttl_seconds = "turn:turn.test:3478", "sh4red", 600
    servers = ice_servers("v-abc", s, now=1_000_000)
    turn = servers[-1]
    assert turn["urls"] == ["turn:turn.test:3478"] and turn["username"] == "1000600:v-abc"
    expected = base64.b64encode(hmac.new(b"sh4red", b"1000600:v-abc", hashlib.sha1).digest()).decode()
    assert turn["credential"] == expected
    s.turn_secret = ""
    assert all("credential" not in x for x in ice_servers("x", s))   # STUN only


def test_operator_takes_over_a_voice_conversation_and_hands_back():
    with TestClient(app) as client:
        owner_h, owner, site = _site(client)
        wid = site["id"]
        editor_h, _ = _join(client, owner_h, "editor")

        with client.websocket_connect("/tenant/live/events") as ops:
            ops.send_json({"token": owner_h["Authorization"].split()[1]})
            assert ops.receive_json()["type"] == "snapshot"

            with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
                sid = ws.receive_json()["payload"]["session_id"]
                joined = _until(ops, _op("visitor_joined", sid))
                assert joined["website_id"] == wid and joined["channel"] == "voice"
                live_now = client.get("/tenant/live", headers=owner_h).json()
                assert [s["session_id"] for s in live_now] == [sid]
                assert live_now[0]["website_name"] == "Live Co" and live_now[0]["takeover"] is None

                # The agent answers; operators see the turn as it happens.
                ws.send_json({"channel": "EVENTS", "type": "text",
                              "payload": {"text": "What does it cost?"}})
                _drain_turn(ws)
                turn = _until(ops, _op("agent_turn", sid))
                assert turn["question"] == "What does it cost?" and turn["answer"]

                # Take over: the visitor is told, the agent stops answering.
                base = f"/tenant/websites/{wid}/live/{sid}"
                tk = client.post(f"{base}/takeover", headers=owner_h)
                assert tk.status_code == 200, tk.text
                assert _until(ws, _is("EVENTS", "operator_joined"))["payload"]["name"] == "Acme"
                assert client.post(f"{base}/takeover", headers=editor_h).status_code == 409
                assert client.post(f"{base}/message", headers=editor_h,
                                   json={"text": "hi"}).status_code == 409

                ws.send_json({"channel": "EVENTS", "type": "text",
                              "payload": {"text": "Can I talk to a person? my email is a@b.co"}})
                _until(ws, _is("STATE", "transcript"))
                said = _until(ops, _op("visitor_message", sid))
                assert said["message"]["text"].startswith("Can I talk to a person")
                r = client.post(f"{base}/message", headers=owner_h,
                                json={"text": "Hi, I'm here. Happy to help with pricing."})
                assert r.status_code == 200
                msg = _until(ws, _is("EVENTS", "operator_message"))
                assert msg["payload"] == {"name": "Acme", "text": "Hi, I'm here. Happy to help with pricing."}

                # A voice call: offer → visitor (with relay servers), answer and ICE → operator.
                assert client.post(f"{base}/call", headers=owner_h,
                                   json={"type": "offer"}).status_code == 422
                client.post(f"{base}/call", headers=owner_h, json={"type": "offer", "sdp": "v=0 offer"})
                offer = _until(ws, _is("EVENTS", "call_offer"))
                assert offer["payload"]["sdp"] == "v=0 offer"
                assert isinstance(offer["payload"]["ice_servers"], list)
                ws.send_json({"channel": "EVENTS", "type": "call_answer", "payload": {"sdp": "v=0 answer"}})
                assert _until(ops, _op("call_answer", sid))["sdp"] == "v=0 answer"
                ws.send_json({"channel": "EVENTS", "type": "call_ice",
                              "payload": {"candidate": {"candidate": "candidate:1 1 udp 1 1.2.3.4 9 typ host"}}})
                assert _until(ops, _op("call_ice", sid))["candidate"]["candidate"].startswith("candidate:1")
                ws.send_json({"channel": "EVENTS", "type": "call_hangup", "payload": {}})
                _until(ops, _op("call_hangup", sid))

                # Hand back: the agent answers again.
                assert client.post(f"{base}/release", headers=owner_h).status_code == 200
                assert _until(ws, _is("EVENTS", "operator_left"))["payload"]["name"] == "Acme"
                ws.send_json({"channel": "EVENTS", "type": "text",
                              "payload": {"text": "Thanks! And how do integrations work?"}})
                _drain_turn(ws)

                conv = client.get(base, headers=owner_h).json()
                senders = [e["sender"] for e in conv["events"]]
                assert senders.count("agent") == 2          # nothing answered during the takeover
                texts = [e["text"] for e in conv["events"]]
                assert "Acme joined" in texts and "Acme handed back to the agent" in texts
                assert any(t.startswith("Voice call ended") for t in texts)
                visitor_live = next(e for e in conv["events"]
                                    if e["sender"] == "visitor" and "person" in e["text"])
                assert "a@b.co" not in visitor_live["text"]   # stored masked (WS8)
                assert conv["takeover"] is None and conv["live"] is True

            # The visitor left.
            _until(ops, _op("visitor_left", sid))
        assert client.get("/tenant/live", headers=owner_h).json() == []

        log = [e["action"] for e in client.get("/tenant/audit", headers=owner_h).json()]
        for action in ("take_over", "send_message", "call_signal", "release"):
            assert action in log, action


def test_takeover_on_the_text_path_and_the_agent_catches_up():
    from app.transport.session_store import store as sessions

    with TestClient(app) as client:
        owner_h, _, site = _site(client)
        key = site["public_key"]
        first = client.post("/chat", json={"message": "Hello", "key": key}).json()
        sid = first["session_id"]
        assert [s["channel"] for s in client.get("/tenant/live", headers=owner_h).json()] == ["text"]

        base = f"/tenant/websites/{site['id']}/live/{sid}"
        assert client.post(f"{base}/takeover", headers=owner_h).status_code == 200
        r = client.post("/chat", json={"message": "Is there a discount?", "key": key,
                                       "session_id": sid}).json()
        assert r["intent"] == "takeover" and r["text"] == "" and r["takeover"]["name"] == "Acme"
        client.post(f"{base}/message", headers=owner_h, json={"text": "Yes, 10% for annual plans."})
        polled = client.get("/chat/live", params={"session_id": sid, "key": key,
                                                  "after": r["takeover"]["after"]}).json()
        assert [m["text"] for m in polled["messages"]] == ["Yes, 10% for annual plans."]
        assert polled["takeover"]["name"] == "Acme"

        client.post(f"{base}/release", headers=owner_h)
        done = client.get("/chat/live", params={"session_id": sid, "key": key,
                                                "after": polled["messages"][-1]["id"]}).json()
        assert done["takeover"] is None
        assert [m["text"] for m in done["messages"]] == ["Acme handed back to the agent"]

        after = client.post("/chat", json={"message": "Great, what's included?", "key": key,
                                           "session_id": sid}).json()
        assert after["intent"] != "takeover" and after["text"]
        import asyncio
        _, state = asyncio.run(sessions.load(sid, site_key=site["site_key"]))
        history = [m.text for m in state.history]
        assert "Is there a discount?" in history
        assert any("10% for annual plans" in t and "Acme" in t for t in history)


def test_operators_only_see_their_own_sites_and_need_a_valid_token():
    with TestClient(app) as client:
        owner_h, _, site = _site(client)
        other_h, _, _ = _site(client)
        with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
            sid = ws.receive_json()["payload"]["session_id"]
            assert client.get("/tenant/live", headers=other_h).json() == []
            assert client.post(f"/tenant/websites/{site['id']}/live/{sid}/takeover",
                               headers=other_h).status_code == 404
            viewer_h, _ = _join(client, owner_h, "viewer")
            assert len(client.get("/tenant/live", headers=viewer_h).json()) == 1
            assert client.post(f"/tenant/websites/{site['id']}/live/{sid}/takeover",
                               headers=viewer_h).status_code == 403
        # A visitor who has left can't be taken over.
        for _ in range(40):
            if not client.get("/tenant/live", headers=owner_h).json():
                break
            time.sleep(0.05)
        assert client.post(f"/tenant/websites/{site['id']}/live/{sid}/takeover",
                           headers=owner_h).status_code == 409
        with client.websocket_connect("/tenant/live/events") as ops:
            ops.send_json({"token": "not-a-token"})
            assert ops.receive_json() == {"type": "error", "reason": "not_authenticated"}


def test_visitor_leaving_ends_the_takeover():
    with TestClient(app) as client:
        owner_h, _, site = _site(client)
        with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
            sid = ws.receive_json()["payload"]["session_id"]
            base = f"/tenant/websites/{site['id']}/live/{sid}"
            client.post(f"{base}/takeover", headers=owner_h)
            _until(ws, _is("EVENTS", "operator_joined"))
        for _ in range(100):   # up to 5 s: the cleanup is async and the suite's DB is busy
            conv = client.get(base, headers=owner_h).json()
            if conv["takeover"] is None and "The visitor left" in [e["text"] for e in conv["events"]]:
                break
            time.sleep(0.05)
        assert conv["takeover"] is None and conv["live"] is False
        assert "The visitor left" in [e["text"] for e in conv["events"]]
