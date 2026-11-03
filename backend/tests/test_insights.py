"""
Insights v1 (WS10): every answered question lands in a per-session transcript;
the console gets top questions, knowledge gaps, the funnel and transcripts.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.insights.store import record_turn
from app.main import app


def _record(site_key: str, question: str, *, found: bool) -> None:
    """Write one turn straight to the store (a throwaway engine, own loop)."""
    async def run() -> None:
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                await record_turn(db, site_key=site_key, session_id="later", channel="text",
                                  question=question, answer="Yes.", intent="capability",
                                  grounding={"found": found, "confidence": 0.8, "sources": []})
                await db.commit()
        finally:
            await engine.dispose()
    asyncio.run(run())


def _tenant(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"in_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_chat_turns_build_insights_and_transcripts():
    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Insight Co"}, headers=h).json()
        base = f"/tenant/websites/{site['id']}"
        app.state.runtime.settings.episodic_min_episodes = 1

        q1 = f"Do you integrate with Zapier {uuid.uuid4().hex[:6]}?"
        sid = None
        for msg in (q1, q1, "hello there"):
            r = client.post("/chat", json={"message": msg, "key": site["public_key"],
                                           "session_id": sid}).json()
            sid = r["session_id"]

        ins = client.get(f"{base}/insights", headers=h).json()
        assert (ins["conversations"], ins["engaged"], ins["turns"]) == (1, 1, 3)
        assert ins["top_questions"][0]["question"] == q1
        assert ins["top_questions"][0]["count"] == 2
        # The tenant has no content yet, so its question is a knowledge gap —
        # small talk is not.
        gaps = [g["question"] for g in ins["gaps"]]
        assert q1 in gaps and "hello there" not in gaps
        assert [f["count"] for f in ins["funnel"]] == [1, 1, 0]
        assert ins["grounded_rate"] == 0.0           # 2 real questions, none grounded

        convs = client.get(f"{base}/conversations", headers=h).json()
        assert convs["total"] == 1 and convs["items"][0]["first_question"] == q1
        assert convs["items"][0]["ungrounded"] == 2      # "hello there" isn't one
        conv = client.get(f"{base}/conversations/{convs['items'][0]['id']}", headers=h).json()
        assert [t["question"] for t in conv["transcript"]] == [q1, q1, "hello there"]
        assert [t["served_from_cache"] for t in conv["transcript"]] == [False, True, False]
        assert [t["unanswered"] for t in conv["transcript"]] == [True, True, False]

        # Once the question gets a grounded answer, the gap closes.
        _record(site["site_key"], q1, found=True)
        ins = client.get(f"{base}/insights", headers=h).json()
        assert q1 not in [g["question"] for g in ins["gaps"]]

        # Another tenant can't read them; deleting the site removes them.
        other = _tenant(client)
        assert client.get(f"{base}/insights", headers=other).status_code == 404
        assert client.get(f"{base}/conversations/{conv['id']}", headers=other).status_code == 404
        assert client.delete(base, headers=h).status_code in (200, 204)


def test_voice_turn_is_recorded():
    site = f"insvoice-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "What does onboarding look like?"}})
            ends = 0
            for _ in range(300):
                env = ws.receive_json()
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                    if ends >= 2:
                        break

        # Recording is fire-and-forget; give it a moment to land.
        from tests.test_lifecycle_guard import _scalar
        for _ in range(40):
            if _scalar("SELECT count(*) FROM conversation_turns WHERE site_key = :s", s=site):
                break
            time.sleep(0.05)
        assert _scalar("SELECT count(*) FROM conversations WHERE site_key = :s "
                       "AND channel = 'voice'", s=site) == 1
