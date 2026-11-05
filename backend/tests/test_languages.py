"""
English + Hindi (M2-7): language detection (Hindi, Hinglish, English), the
reply-language rules, Hindi answers that search the English knowledge,
caches kept apart by language, and the site's language settings.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.i18n.detect import choose, detect, speech_code
from app.main import app
from app.transport.answer_audio import audio_key

def _has_hindi(s: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in s or "")


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
        "email": f"lang_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


# ---- detection set ---------------------------------------------------------

DETECTION_SET = [
    # Hindi in Devanagari, including English product words inside it
    ("HireBuddha की कीमत क्या है?", "hi"),
    ("मुझे डेमो चाहिए", "hi"),
    ("क्या यह Salesforce के साथ काम करता है?", "hi"),
    ("आपका डेटा कहाँ स्टोर होता है?", "hi"),
    ("50 लोगों की टीम के लिए pricing बताइए", "hi"),
    ("नमस्ते", "hi"),
    # Hinglish: Hindi in Latin letters
    ("pricing kya hai?", "hinglish"),
    ("ye kaise kaam karta hai", "hinglish"),
    ("mujhe demo chahiye", "hinglish"),
    ("kitna paisa lagega 10 logon ke liye", "hinglish"),
    ("kya aap Zoho ke saath integrate karte ho", "hinglish"),
    ("kaise?", "hinglish"),
    ("hindi mein bolo", "hinglish"),
    # English, including words that look like Hindi on their own
    ("What does it cost?", "en"),
    ("How do I log in to the dashboard?", "en"),
    ("Hi there", "en"),
    ("Do you integrate with HubSpot and Salesforce?", "en"),
    ("Can you show me the pricing for a 50 seat team aur integrations bhi", "en"),
    ("Is the data stored in India?", "en"),
    ("", "en"),
]


@pytest.mark.parametrize("text,expected", DETECTION_SET)
def test_detection_set(text, expected):
    assert detect(text) == expected


def test_reply_language_rules():
    both = ["en", "hi"]
    # A site without Hindi always answers in English.
    assert choose("मुझे डेमो चाहिए", enabled=["en"])[0].reply == "en"
    # Devanagari → Hindi; English → English; Hinglish → simple English.
    assert choose("मुझे डेमो चाहिए", enabled=both)[0].reply == "hi"
    assert choose("What does it cost?", enabled=both)[0].reply == "en"
    c, pref = choose("pricing kya hai?", enabled=both)
    assert (c.reply, c.seen, pref) == ("en", "hinglish", None)
    # ...unless the visitor prefers Hindi: their widget is Hindi, or they wrote Devanagari before.
    assert choose("pricing kya hai?", enabled=both, ui="hi")[0].reply == "hi"
    assert choose("pricing kya hai?", enabled=both, used_hindi=True)[0].reply == "hi"
    # Asking for a language sets it for the rest of the conversation.
    c, pref = choose("please reply in Hindi", enabled=both)
    assert (c.reply, pref) == ("hi", "hi")
    assert choose("What about security?", enabled=both, pref=pref)[0].reply == "hi"
    c, pref = choose("अंग्रेज़ी में बताइए", enabled=both, pref="hi")
    assert (c.reply, pref) == ("en", "en")
    assert speech_code("hi") == "hi-IN" and speech_code("en") == "en-IN"


def test_audio_cache_keys_separate_languages():
    base = dict(voice="Aoede", sample_rate=24000)
    assert audio_key("नमस्ते", **base) != audio_key("नमस्ते", **base, language="hi-IN")
    # English keys are unchanged (no language pinned), so the existing cache stays valid.
    assert audio_key("Hello", **base) == audio_key("Hello", **base, language="")


def test_answer_cache_is_kept_apart_by_language():
    rt_settings = get_settings()
    site = f"lang-{uuid.uuid4().hex[:8]}"

    async def go(db):
        from app.cortex.episodic import EpisodicCache
        from app.cortex.providers import build_cortex_providers
        cache = EpisodicCache(db, rt_settings, build_cortex_providers(rt_settings), site_key=site)
        await cache.record(question="What does it cost?", answer_text="It starts at 999.", lang="en")
        await cache.record(question="What does it cost?", answer_text="यह 999 से शुरू होता है।", lang="hi")
        en = await cache.query(transcript="What does it cost?", lang="en")
        hi = await cache.query(transcript="What does it cost?", lang="hi")
        await db.execute(text("DELETE FROM conversation_cache WHERE site_key=:s"), {"s": site})
        await db.commit()
        return en, hi
    en, hi = _run(go)
    assert en[0].answer_text == "It starts at 999." and en[0].match == "exact"
    assert hi[0].answer_text.startswith("यह 999") and all(_has_hindi(h.answer_text) for h in hi)


# ---- the site's settings and a Hindi conversation ------------------------

def test_hindi_conversation_on_a_hindi_site(monkeypatch):
    import app.orchestrator.lean as lean

    searched: list[str] = []
    real = lean.query_cortex

    async def spy(bridge, query, **kw):
        searched.append(query)
        return await real(bridge, query, **kw)
    monkeypatch.setattr(lean, "query_cortex", spy)

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Bhasha Co", "domain": "bhasha.example"},
                           headers=h).json()
        wid, key = site["id"], site["public_key"]
        base = f"/tenant/websites/{wid}/profile"

        # English only by default: a Hindi question gets an English answer.
        prof = client.get(base, headers=h).json()
        assert prof["languages"] == ["en"] and prof["widget_language"] == "auto"
        r = client.post("/chat", json={"message": "आप क्या करते हैं?", "key": key}).json()
        assert r["lang"] == "en" and not _has_hindi(r["text"])

        # Settings are checked.
        for bad in ({"languages": ["en", "fr"]}, {"widget_language": "ta"}):
            assert client.put(base, json=bad, headers=h).status_code == 422
        prof = client.put(base, json={"languages": ["hi"], "widget_language": "hi",
                                      "greeting_hi": "नमस्ते! पूछिए जो पूछना है।"}, headers=h).json()
        assert prof["languages"] == ["en", "hi"]          # English is always on
        assert client.get("/widget/config", params={"key": key}).json()["languages"] == ["en", "hi"]
        enrol = client.post("/experiment/enroll", content='{"key": "%s", "visitor": "visitor-hindi-1"}' % key,
                            headers={"Content-Type": "text/plain"}).json()
        assert enrol["defaults"]["widget_language"] == "hi"
        assert enrol["defaults"]["greeting_hi"].startswith("नमस्ते")

        # A Devanagari question: Hindi answer, retrieval searched in English.
        searched.clear()
        q = "आपकी कीमत क्या है? " + uuid.uuid4().hex[:4]
        r = client.post("/chat", json={"message": q, "key": key, "lang": "hi"}).json()
        assert r["lang"] == "hi" and _has_hindi(r["text"])
        assert r["ack"] and _has_hindi(r["ack"])
        assert searched and searched[-1].isascii() and "price" in searched[-1]
        sid = r["session_id"]

        # Hinglish in a conversation that has used Hindi stays in Hindi...
        r = client.post("/chat", json={"message": "aur demo kaise milega", "key": key,
                                       "session_id": sid}).json()
        assert r["lang"] == "hi"
        # ...and "English please" switches, and sticks.
        r = client.post("/chat", json={"message": "English please, what integrations do you have?",
                                       "key": key, "session_id": sid}).json()
        assert r["lang"] == "en" and not _has_hindi(r["text"])
        r = client.post("/chat", json={"message": "aur security kaisi hai", "key": key,
                                       "session_id": sid}).json()
        assert r["lang"] == "en"

        # Plain Hinglish from a new visitor with an English widget: simple English.
        r = client.post("/chat", json={"message": "pricing kya hai bhai", "key": key, "lang": "en"}).json()
        assert r["lang"] == "en" and not _has_hindi(r["text"])

        # Insights counts questions by the language they were asked in.
        sig = client.get(f"/tenant/websites/{wid}/insights/signals", headers=h).json()
        langs = {x["lang"]: x["turns"] for x in sig["languages"]}
        assert langs.get("hi", 0) >= 2 and langs.get("hinglish", 0) >= 2 and langs.get("en", 0) >= 1


def test_voice_session_speaks_hindi(monkeypatch):
    """A Hindi widget opens in Hindi (the site's Hindi greeting), a Devanagari
    question gets Hindi speech, and switching to English tells the widget."""
    import app.transport.websocket as ws_mod

    spoken: list[tuple[str, str]] = []

    class _TTS:
        sample_rate = 24000

        async def synthesize_stream(self, text, language=""):
            spoken.append((text, language))
            yield b"\x00\x00" * 480

    with TestClient(app) as client:
        h = _tenant(client)
        site = client.post("/tenant/websites", json={"name": "Awaaz Co"}, headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/profile", headers=h,
                   json={"languages": ["en", "hi"], "greeting_hi": "नमस्ते, मैं प्रज्ञा हूँ।"})
        client.put(f"/tenant/websites/{site['id']}/privacy", headers=h, json={
            **client.get(f"/tenant/websites/{site['id']}/privacy", headers=h).json(),
            "consent_required": False})
        monkeypatch.setattr(client.app.state.runtime.engines, "tts", _TTS())
        monkeypatch.setattr(client.app.state.runtime.settings, "audio_cache_enabled", False)

        def until_answer(ws):
            texts, events = [], []
            ends = 0
            for _ in range(400):
                env = ws.receive_json()
                if env["channel"] == "EVENTS":
                    events.append(env)
                if env["channel"] == "AUDIO" and env["type"] == "start" and env["payload"].get("text"):
                    texts.append(env["payload"]["text"])
                if env["channel"] == "AUDIO" and env["type"] == "end" and \
                        not (env.get("sync_id") or "").startswith("ack_"):
                    ends += 1
                    if ends >= 1 and texts and not texts[-1].startswith(("एक पल", "Let me")):
                        return texts, events
            return texts, events

        with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
            ws.receive_json()                                   # ready
            ws.send_json({"channel": "EVENTS", "type": "hello", "payload": {"lang": "hi", "tour": False}})
            texts, _ = until_answer(ws)
            assert texts[-1] == "नमस्ते, मैं प्रज्ञा हूँ।"
            assert ("नमस्ते, मैं प्रज्ञा हूँ।", "hi-IN") in spoken

            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "आप क्या करते हैं? " + uuid.uuid4().hex[:4]}})
            texts, events = until_answer(ws)
            assert _has_hindi(texts[-1])
            assert not any(e["type"] == "language" for e in events)   # already Hindi
            assert any(lang == "hi-IN" and _has_hindi(t) for t, lang in spoken)

            spoken.clear()
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "What does your product do? " + uuid.uuid4().hex[:4]}})
            texts, events = until_answer(ws)
            assert {"lang": "en"} in [e["payload"] for e in events if e["type"] == "language"]
            assert not _has_hindi(texts[-1])
            assert all(lang == "" for _, lang in spoken)          # English: no language pinned
