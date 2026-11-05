"""
Follow-ups that close the "left" items of earlier M2 epics.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
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


def _register(client: TestClient) -> tuple[dict, dict]:
    body = client.post("/auth/register", json={
        "email": f"fu_{uuid.uuid4().hex[:10]}@example.com", "password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


# ---- M2-2: the hot-lead alert opens the visitor's conversation --------------------------

def test_slack_alert_links_to_the_exact_conversation():
    from app.leads.delivery import _slack_text

    lead = {"name": "Asha", "email": "asha@example.com", "company": "Acme", "score": 90,
            "summary": "Wants pricing", "source": "conversation", "session_id": "sess 42/x"}
    assert "/live?session=sess%2042%2Fx|" in _slack_text(lead)
    assert "/live|" in _slack_text({**lead, "session_id": None})
    assert "/live" not in _slack_text({**lead, "source": "form"})


# ---- M2-5: labelling cost is counted, as background (never a conversation) ----------------

def test_classification_cost_goes_on_usage_but_not_on_turns_or_billing():
    from app.insights.classify import classify_pending

    class FakeLLM:
        async def generate(self, **kw):
            from app.ai.base import LLMResponse
            return LLMResponse(text='{"objections": ["price"], "competitors": [], '
                                    '"feature_request": null, "buying_signal": false}',
                               input_tokens=120, output_tokens=30)

    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Cost Co"}, headers=h).json()
    sk = site["site_key"]

    async def go(db):
        await db.execute(text(
            "INSERT INTO conversations (id, site_key, session_id, started_at, last_at, turns) "
            "VALUES (:id, :s, 'c1', now(), now(), 1)"), {"id": uuid.uuid4(), "s": sk})
        conv = (await db.execute(text("SELECT id FROM conversations WHERE site_key = :s"),
                                 {"s": sk})).scalar_one()
        await db.execute(text(
            "INSERT INTO conversation_turns (id, conversation_id, site_key, question, answer, found, "
            "q_norm, created_at) VALUES (:id, :c, :s, 'Too expensive', 'ok', true, 'too expensive', now())"),
            {"id": uuid.uuid4(), "c": conv, "s": sk})
        await db.commit()
        # Other sites' pending turns may be labelled too; ours is among the newest.
        await classify_pending(db, llm=FakeLLM(), model="fast", batch=200)
        return (await db.execute(text(
            "SELECT channel, session_id, fast_in_tok, fast_out_tok, total_cost FROM usage_events "
            "WHERE site_key = :s"), {"s": sk})).mappings().all()

    rows = _db(go)
    assert len(rows) == 1
    r = rows[0]
    assert r["channel"] == "background" and r["session_id"] is None
    assert (r["fast_in_tok"], r["fast_out_tok"]) == (120, 30) and r["total_cost"] > 0

    with TestClient(app) as client:
        a = client.get(f"/tenant/websites/{site['id']}/analytics", headers=h).json()
    assert a["totals"]["turns"] == 0 and a["totals"]["total_cost"] > 0


# ---- M2-5: feature requests grouped by meaning --------------------------------------------

def test_feature_requests_group_by_meaning_when_embeddings_exist():
    from app.insights.store import group_requests

    items = [{"text": "Native Shopify integration", "at": "3"},
             {"text": "Can you plug into my online store platform?", "at": "2"},
             {"text": "Dark mode for the widget", "at": "1"}]
    # Without vectors: no shared words, three groups.
    assert len(group_requests(items)) == 3
    # With vectors: the first two mean the same thing.
    vecs = [[1.0, 0.1, 0.0], [0.95, 0.15, 0.02], [0.0, 0.0, 1.0]]
    groups = group_requests(items, vectors=vecs)
    assert [g["count"] for g in groups] == [2, 1]
    assert groups[0]["text"] == "Native Shopify integration"


# ---- M2-3: the agent writes a trigger's message for the page -----------------------------

def test_trigger_message_written_for_the_page_and_cached():
    from app.triggers import compose

    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Compose Co"}, headers=h).json()
        rule = client.post(f"/tenant/websites/{site['id']}/triggers", headers=h, json={
            "name": "Pricing dwell", "kind": "time_on_page", "seconds": 10, "pages": ["/pricing*"],
            "message": "Need help choosing?", "compose": True}).json()
        assert rule["compose"] is True
        q = {"key": site["public_key"], "rule_id": rule["id"]}
        r = client.get("/widget/triggers/message", params={**q, "page": "/pricing?x=1",
                                                          "title": "Pricing | Compose Co"})
        assert r.json() == {"message": "Questions about Pricing? I can answer them right here."}
        hi = client.get("/widget/triggers/message", params={**q, "page": "/pricing", "lang": "hi",
                                                           "title": "Pricing | Compose Co"}).json()
        assert "के बारे में" in hi["message"]
        # Outside the rule's pages, or for a bot: the fixed message.
        assert client.get("/widget/triggers/message", params={**q, "page": "/blog"}).json()["message"] \
            == "Need help choosing?"
        assert client.get("/widget/triggers/message", params={**q, "page": "/pricing/teams"},
                          headers={"User-Agent": "Googlebot/2.1"}).json()["message"] == "Need help choosing?"
        # Cached per page and language; editing the rule clears it.
        n = _db(lambda db: _count(db, rule["id"]))
        assert n == 2
        client.put(f"/tenant/websites/{site['id']}/triggers/{rule['id']}", headers=h, json={
            "name": "Pricing dwell", "kind": "time_on_page", "seconds": 10, "pages": ["/pricing*"],
            "message": "Want a hand?", "compose": True})
        assert _db(lambda db: _count(db, rule["id"])) == 0
        # A rule without compose always gets its own words.
        plain = client.post(f"/tenant/websites/{site['id']}/triggers", headers=h, json={
            "name": "Plain", "kind": "exit_intent", "message": "Before you go…"}).json()
        assert client.get("/widget/triggers/message", params={
            "key": site["public_key"], "rule_id": plain["id"], "page": "/x", "title": "X"}).json() \
            == {"message": "Before you go…"}
    assert compose.tidy('  "Comparing plans?  Ask me."  ') == "Comparing plans? Ask me."
    assert compose.page_matches("/pricing/teams", ["/pricing*"]) and not compose.page_matches("/blog", ["/pricing"])


async def _count(db, rule_id):
    return (await db.execute(text("SELECT count(*) FROM trigger_messages WHERE rule_id = :r"),
                             {"r": rule_id})).scalar()


# ---- M2-6: "send me this" by voice -------------------------------------------------------

def test_recap_phrases_and_spoken_email_addresses():
    from app.recaps.intent import email_in, wants_recap

    for said in ("Can you send me this?", "please email me a recap", "give me the summary",
                 "इसे मुझे भेज दो", "ye mujhe bhej do", "recap please"):
        assert wants_recap(said), said
    for said in ("What does this cost?", "Send me to the pricing page", "Can I share access with my team?"):
        assert not wants_recap(said), said
    assert email_in("email me a recap at asha.k at example dot co dot in") == "asha.k@example.co.in"
    assert email_in("send it to Ravi@Example.com please") == "Ravi@Example.com"
    assert email_in("send me this") is None


def test_a_spoken_recap_request_goes_to_the_widget_not_the_agent():
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Voice Recap Co"}, headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/privacy", headers=h, json={
            **client.get(f"/tenant/websites/{site['id']}/privacy", headers=h).json(),
            "consent_required": False})
        with client.websocket_connect(f"/ws/voice?key={site['public_key']}") as ws:
            assert ws.receive_json()["type"] == "ready"
            ws.send_json({"channel": "EVENTS", "type": "text",
                          "payload": {"text": "email me a recap at asha at example dot com"}})
            seen = []
            for _ in range(50):
                env = ws.receive_json()
                seen.append(env)
                if env["channel"] == "EVENTS" and env["type"] == "recap_request":
                    break
            assert env["type"] == "recap_request" and env["payload"]["email"] == "asha@example.com"
            assert any(e["channel"] == "STATE" and e["type"] == "transcript" for e in seen)
            assert not any(e["channel"] == "AUDIO" for e in seen), "no agent turn for it"


# ---- M2-8: answering an action card by voice; embeds on recap pages ----------------------

def test_spoken_yes_and_no_for_an_action_card():
    from app.actions.voice import answer

    for yes in ("Yes", "yes please", "Go ahead.", "confirm", "okay do it", "haan ji", "हाँ", "ठीक है", "theek hai"):
        assert answer(yes) is True, yes
    for no in ("No", "no thanks", "cancel", "not now", "nahin", "नहीं", "रहने दो"):
        assert answer(no) is False, no
    for other in ("yes but how much is the enterprise plan", "what about the annual price?",
                  "no I meant the growth plan for twenty people", "", "maybe"):
        assert answer(other) is None, other


def test_recap_pages_may_frame_only_the_embeds_they_show():
    from app.recaps import page

    recap = {"content": {"turns": [{"components": [
        {"component_type": "embed", "initial_state": {"src": "https://tools.acme.com/cfg?x=1"}},
        {"component_type": "embed", "initial_state": {"src": "http://plain.example"}},
        {"component_type": "embed", "initial_state": {"src": "javascript:alert(1)"}},
        {"component_type": "chart", "initial_state": {}}]}]}}
    assert page.embed_origins(recap) == ["https://tools.acme.com"]
    assert "frame-src https://tools.acme.com;" in page.csp("https://cdn.example/dist", page.embed_origins(recap))
    assert "frame-src" not in page.csp("https://cdn.example/dist", [])


def test_money_components_carry_the_sites_currency():
    from app.orchestrator.components import normalize_component

    ctype, st = normalize_component("roi_calculator", {"seats": 5}, site_key="hirebuddha")
    assert st["currency"] == "INR"
    assert normalize_component("configurator", {"currency": "USD"}, site_key="hirebuddha")[1]["currency"] == "USD"
    assert "currency" not in normalize_component("chart", {}, site_key="hirebuddha")[1]


def test_new_education_site_has_hindi_starters_and_its_agent_name_for_the_widget():
    import json as _json

    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Vidya", "template": "education"}, headers=h).json()
        client.put(f"/tenant/websites/{site['id']}/profile", json={"agent_name": "Mira"}, headers=h)
        d = client.post("/experiment/enroll", content=_json.dumps({"key": site["public_key"], "visitor": "visitor-hi-1"}),
                        headers={"Content-Type": "text/plain"}).json()["defaults"]
    assert d["agent_name"] == "Mira"
    assert d["starters_hi"] and all(any("ऀ" <= ch <= "ॿ" for ch in q) for q in d["starters_hi"])


def test_quote_request_pdf():
    from app.actions.pdf import quote_pdf

    run = {"id": "3f2a9c1e-0000-0000-0000-000000000000", "created_at": "2026-11-05T10:30:00+00:00",
           "summary": [{"label": "Email", "value": "asha@example.com"},
                       {"label": "Needs", "value": "200 seats (annual), SSO (Okta) and a ₹ invoice " * 3},
                       {"label": "Name", "value": "आशा"}]}
    pdf = quote_pdf(company="Acme (India)", action_label="Get a quote", run=run)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert b"(Quote request: Get a quote) Tj" in pdf
    assert b"Acme \(India\)" in pdf                       # parentheses escaped
    assert b"Rs. " in pdf and b"asha@example.com" in pdf
    assert b"05 Nov 2026, 10:30 UTC" in pdf and b"3F2A9C1E" in pdf
    # The xref offsets point at the objects.
    start = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    assert pdf[start:start + 4] == b"xref"
    first = int(pdf[start:].split(b"\n")[3][:10])
    assert pdf[first:first + 7] == b"1 0 obj"


def test_quote_pdf_download_only_for_done_quote_runs():
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "Quote Co"}, headers=h).json()
        r = client.get(f"/tenant/websites/{site['id']}/action-runs/{uuid.uuid4()}/quote.pdf", headers=h)
        assert r.status_code == 404
