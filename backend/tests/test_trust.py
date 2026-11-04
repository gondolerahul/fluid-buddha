"""
Trust layer (WS8): PII is masked before the model and before storage, the
microphone needs the visitor's consent, visitor data expires per site, a
visitor's data can be erased, and cached answers can be pinned or blocked.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.leads.store import LeadIn
from app.main import app
from app.transport.session_store import store
from app.trust.pii import PiiVault, contains_pii, redact
from app.trust.retention import purge_expired
from tests.test_lifecycle_guard import _scalar

CARD = "4111 1111 1111 1111"   # a published test card number (passes Luhn)


def _tenant_site(client: TestClient, name: str = "Trust Co") -> tuple[dict, dict]:
    tok = client.post("/auth/register", json={
        "email": f"tr_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    return h, client.post("/tenant/websites", json={"name": name}, headers=h).json()


def _run(fn):
    """Run ``fn(db)`` on a throwaway engine (never the app's shared pool)."""
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                out = await fn(db)
                await db.commit()
                return out
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_vault_masks_and_restores():
    v = PiiVault()
    masked = v.mask(f"I'm jo@acme.io, call +1 415 555 0100, card {CARD}, ssn 123-45-6789")
    assert masked == ("I'm <EMAIL_1>, call <PHONE_1>, card <CARD_1>, ssn <SSN_1>")
    assert v.mask("again: jo@acme.io") == "again: <EMAIL_1>"   # same value, same token
    assert v.unmask_args({"email": "<email_1>", "n": 3}) == {"email": "jo@acme.io", "n": 3}
    assert PiiVault.spoken("Thanks, I noted <EMAIL_1>.") == "Thanks, I noted your email."
    assert v.stored("reach me at <EMAIL_1>") == "reach me at [email]"
    assert redact("IBAN DE89 3704 0044 0532 0130 00 please") == "IBAN [bank account] please"
    # Ordinary numbers are not PII.
    for plain in ("We have 1,200 employees", "Plans for 2024-2025", "about 100.000.000 rows",
                  "order 12345", "card 4111 1111 1111 1112"):
        assert v.mask(plain) == plain and not contains_pii(plain), plain
    off = PiiVault(enabled=False)
    assert off.mask("jo@acme.io") == "jo@acme.io"


def test_lead_text_never_keeps_card_numbers():
    lead = LeadIn(email="a@b.co", message=f"Bill {CARD} or call 415-555-0100").cleaned()
    assert lead.message == "Bill [card number] or call 415-555-0100"


def test_chat_masks_pii_before_the_model_and_storage():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        msg = "Contact me at jo@acme.io or +1 415 555 0100 about pricing"
        r = client.post("/chat", json={"message": msg, "key": site["public_key"]}).json()
        assert "jo@acme.io" not in r["text"] and "<EMAIL" not in r["text"]

        # What the model sees next turn (the history) holds placeholders only.
        sid, state = asyncio.run(store.load(r["session_id"], site_key=site["site_key"]))
        assert sid == r["session_id"]
        assert "<EMAIL_1>" in state.history[0].text and "acme.io" not in state.history[0].text

        # The lead still gets the real address the visitor typed.
        lead = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"][0]
        assert lead["email"] == "jo@acme.io"

        # Transcripts store labels; the personal turn is not cached for replay.
        sk = site["site_key"]
        assert _scalar("SELECT count(*) FROM conversation_turns WHERE site_key=:s "
                       "AND question LIKE '%[email]%[phone]%'", s=sk) == 1
        assert _scalar("SELECT count(*) FROM conversation_turns WHERE site_key=:s "
                       "AND (question LIKE '%acme.io%' OR question LIKE '%555%')", s=sk) == 0
        assert _scalar("SELECT count(*) FROM conversation_cache WHERE site_key=:s", s=sk) == 0


def test_masking_can_be_turned_off_per_site():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        base = f"/tenant/websites/{site['id']}/privacy"
        cfg = client.get(base, headers=h).json()
        assert cfg == {"redact_pii": True, "consent_required": True, "privacy_policy_url": None,
                       "transcript_retention_days": 90, "lead_retention_days": 0, "recap_days": 90}
        client.put(base, headers=h, json={**cfg, "redact_pii": False}).raise_for_status()
        client.post("/chat", json={"message": "Write to jo@acme.io please",
                                   "key": site["public_key"]})
        assert _scalar("SELECT count(*) FROM conversation_turns WHERE site_key=:s "
                       "AND question LIKE '%jo@acme.io%'", s=site["site_key"]) == 1


def test_privacy_settings_are_validated_and_public():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        base = f"/tenant/websites/{site['id']}/privacy"
        good = {"redact_pii": True, "consent_required": False,
                "privacy_policy_url": "https://example.com/privacy",
                "transcript_retention_days": 30, "lead_retention_days": 365}
        for bad in ({"privacy_policy_url": "javascript:alert(1)"},
                    {"transcript_retention_days": 45}, {"lead_retention_days": -1}):
            assert client.put(base, headers=h, json={**good, **bad}).status_code == 422
        # recap_days (M2-6) is optional and defaults to 90.
        assert client.put(base, headers=h, json=good).json() == {**good, "recap_days": 90}
        cfg = client.get("/widget/config", params={"key": site["public_key"]}).json()
        assert cfg["privacy"] == {"consent_required": False,
                                  "policy_url": "https://example.com/privacy",
                                  "retention_days": 30, "redacts_pii": True}
        # Another tenant can't read or change it.
        other, _ = _tenant_site(client, "Other Co")
        assert client.get(base, headers=other).status_code == 404


def test_microphone_audio_waits_for_consent():
    site = f"consent-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/voice?site={site}") as ws:
            ready = ws.receive_json()
            assert ready["payload"]["privacy"]["consent_required"] is True
            ws.send_json({"channel": "AUDIO", "type": "start", "payload": {}})
            env = ws.receive_json()
            assert (env["channel"], env["type"]) == ("EVENTS", "consent_required")

            ws.send_json({"channel": "EVENTS", "type": "consent", "payload": {"mic": True}})
            ws.send_json({"channel": "AUDIO", "type": "start", "payload": {}})
            ws.send_json({"channel": "AUDIO", "type": "end",
                          "payload": {"transcript": "What does onboarding look like?"}})
            ends = 0
            for _ in range(300):
                env = ws.receive_json()
                assert env["type"] != "consent_required"
                if env["channel"] == "AUDIO" and env["type"] == "end":
                    ends += 1
                    if ends >= 2:
                        break
        for _ in range(40):
            if _scalar("SELECT count(*) FROM conversations WHERE site_key=:s", s=site):
                break
            time.sleep(0.05)
        assert _scalar("SELECT count(*) FROM conversations WHERE site_key=:s "
                       "AND consent_at IS NOT NULL", s=site) == 1


def test_retention_sweep_respects_each_site():
    keep, short = f"keep-{uuid.uuid4().hex[:8]}", f"short-{uuid.uuid4().hex[:8]}"

    async def seed(db):
        await db.execute(text(
            "INSERT INTO site_privacy (site_key, transcript_retention_days, lead_retention_days) "
            "VALUES (:k, 0, 0), (:s, 30, 90)"), {"k": keep, "s": short})
        for sk in (keep, short):
            for age in (5, 60, 120):
                await db.execute(text(
                    "INSERT INTO conversations (id, site_key, session_id, last_at) "
                    "VALUES (:id, :s, :sid, now() - :d * interval '1 day')"),
                    {"id": uuid.uuid4(), "s": sk, "sid": f"s{age}", "d": age})
                await db.execute(text(
                    "INSERT INTO leads (id, site_key, email, created_at) "
                    "VALUES (:id, :s, 'a@b.co', now() - :d * interval '1 day')"),
                    {"id": uuid.uuid4(), "s": sk, "d": age})
            for status in ("auto", "pinned", "blocked"):
                await db.execute(text(
                    "INSERT INTO conversation_cache (id, site_key, q_norm, question, "
                    "answer_text, status, created_at) VALUES (:id, :s, 'q', 'q', 'a', :st, "
                    "now() - interval '60 days')"), {"id": uuid.uuid4(), "s": sk, "st": status})
        return await purge_expired(db)

    removed = _run(seed)
    assert removed["conversations"] >= 2 and removed["leads"] >= 1
    count = lambda t, s: _scalar(f"SELECT count(*) FROM {t} WHERE site_key=:s", s=s)  # noqa: E731
    assert (count("conversations", keep), count("leads", keep)) == (3, 3)
    assert (count("conversations", short), count("leads", short)) == (1, 2)
    assert count("conversation_cache", keep) == 3
    # Only the auto answer expires; pinned and blocked are the tenant's own.
    assert _scalar("SELECT count(*) FROM conversation_cache WHERE site_key=:s "
                   "AND status <> 'auto'", s=short) == 2
    assert count("conversation_cache", short) == 2


def test_erase_a_visitor():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        client.post("/chat", json={"message": "Email me at gone@acme.io",
                                   "key": site["public_key"]})
        client.post("/chat", json={"message": "Email me at stays@acme.io",
                                   "key": site["public_key"]})
        base = f"/tenant/websites/{site['id']}/privacy/erase"
        assert client.post(base, headers=h, json={"email": "nope"}).status_code == 422
        assert client.post(base, headers=h, json={"email": "Gone@Acme.io"}).json() == {
            "leads": 1, "conversations": 1}
        emails = [lead["email"] for lead in
                  client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()["items"]]
        assert emails == ["stays@acme.io"]


def test_pinned_answers_replay_and_blocked_ones_never_do():
    with TestClient(app) as client:
        h, site = _tenant_site(client)
        # Far more history than this site has, so only a pinned answer replays.
        app.state.runtime.settings.episodic_min_episodes = 50
        ask = lambda: client.post("/chat", json={  # noqa: E731
            "message": "What does onboarding look like?", "key": site["public_key"]}).json()
        cache = f"/tenant/websites/{site['id']}/cache"

        assert ask()["intent"] != "cached"
        [entry] = client.get(cache, headers=h).json()["items"]
        assert entry["status"] == "auto"
        assert client.put(f"{cache}/{entry['id']}", headers=h,
                          json={"status": "pinned"}).json()["status"] == "pinned"
        assert ask()["intent"] == "cached"

        client.put(f"{cache}/{entry['id']}", headers=h, json={"status": "blocked"})
        app.state.runtime.settings.episodic_min_episodes = 1
        assert ask()["intent"] != "cached"
        # The blocked question is answered fresh and not cached again.
        assert client.get(cache, headers=h).json()["total"] == 1
        assert client.get(cache, headers=h,
                          params={"status_filter": "blocked"}).json()["total"] == 1
        assert client.put(f"{cache}/{entry['id']}", headers=h,
                          json={"status": "nope"}).status_code == 422
