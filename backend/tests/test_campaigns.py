"""
Generative landing pages (M3-1): campaign validation, grounded composition
(sources, numbers, proof, pinned and blocked answers), cache keys and cache
hits, two personas → two pages, the model path checked like the rules path,
conversions (form, CTA), engagement, analytics with a variant, previews of
drafts, embedding, and site deletion.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.campaigns import compose
from app.campaigns import store as campaigns
from app.config import get_settings
from app.main import app

PW = "supersecret1"
KNOWLEDGE = (
    "Orbit is a scheduling platform for clinics and hospitals. "
    "Doctors see their whole week on one screen and patients book online at any hour. "
    "The Starter plan costs 4,999 rupees a month for 5 doctors. "
    "The Growth plan costs 14,999 rupees a month for 25 doctors and includes WhatsApp reminders. "
    "Hospital IT teams get single sign-on with Azure AD and an audit log of every change. "
    "Clinic owners cut no-shows because reminders go out automatically the day before."
)


def _sql(q, p=None):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                res = await db.execute(text(q), p or {})
                await db.commit()
                try:
                    return res.mappings().all()
                except Exception:
                    return None
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _site(client, *, domain=None):
    body = client.post("/auth/register", json={"email": f"cmp_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": PW}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    site = client.post("/tenant/websites", json={"name": "Orbit", **({"domain": domain} if domain else {})},
                       headers=h).json()
    w = f"/tenant/websites/{site['id']}"
    client.put(f"{w}/profile", headers=h, json={"personas": [
        {"slug": "clinic-owner", "label": "Clinic owners", "focus": "no-shows, reminders and booking"},
        {"slug": "hospital-it", "label": "Hospital IT", "focus": "single sign-on, Azure AD, audit log"}]})
    assert client.post(f"{w}/sources", headers=h, json={"kind": "text", "name": "About Orbit",
                                                        "content": KNOWLEDGE}).status_code == 201
    assert client.post(f"{w}/ingestion/run?wait=true", headers=h).json()["status"] == "done"
    return h, site, w


BRIEF = {
    "name": "Orbit for healthcare", "status": "live", "goal": "Book demos with clinics",
    "audience": "Clinics and hospitals in India",
    "key_messages": ["Scheduling that fills every slot", "Patients book online at any hour",
                     "Reminders cut no-shows", "Single sign-on for hospital IT"],
    "cta_label": "Book a demo", "cta_url": "https://orbit.example.com/demo",
    "testimonials": [{"quote": "No-shows halved in a month.", "name": "Dr Rao", "role": "Clinic owner"}],
    "logos": [{"src": "https://cdn.example.com/apollo.svg", "alt": "Apollo"}],
    "sections": ["feature_grid", "text", "testimonials", "logos", "faq", "roi_calculator", "enquiry_form"],
}


def _create(client, h, w, **over):
    r = client.post(f"{w}/campaigns", headers=h, json={**BRIEF, **over})
    assert r.status_code == 201, r.text
    return r.json()


def _path(site, c, **q):
    from urllib.parse import urlencode
    return f"/p/{site['site_key']}/{c['slug']}" + (("?" + urlencode(q)) if q else "")


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0"}


def test_campaign_validation_and_crud():
    with TestClient(app) as client:
        h, site, w = _site(client)
        bad = [({"name": ""}, "name"), ({"slug": "Bad Slug!"}, "link name"), ({"cta_url": "http://x.com"}, "https"),
               ({"persona": "nobody"}, "personas"), ({"status": "archived"}, "Status")]
        for over, words in bad:
            r = client.post(f"{w}/campaigns", headers=h, json={**BRIEF, **over})
            assert r.status_code == 422 and words in r.text, (over, r.text)
        c = _create(client, h, w, sections=["faq", "nonsense", "faq"])
        assert c["slug"] == "orbit-for-healthcare" and c["sections"] == ["faq"]
        assert c["url"].endswith(f"/p/{site['site_key']}/orbit-for-healthcare") and "?preview=" in c["preview_url"]
        assert "<iframe" in c["embed_snippet"]
        assert client.post(f"{w}/campaigns", headers=h, json=BRIEF).status_code == 422  # same slug
        listed = client.get(f"{w}/campaigns", headers=h).json()
        assert [x["id"] for x in listed["campaigns"]] == [c["id"]]
        assert {p["slug"] for p in listed["personas"]} == {"clinic-owner", "hospital-it"}
        assert "roi_calculator" in {s["type"] for s in listed["sections"]}
        upd = client.put(f"{w}/campaigns/{c['id']}", headers=h, json={**BRIEF, "status": "paused"}).json()
        assert upd["status"] == "paused" and upd["version"] == 2     # copy changed (sections)
        same = client.put(f"{w}/campaigns/{c['id']}", headers=h, json={**BRIEF, "status": "live"}).json()
        assert same["version"] == 2                                   # status alone doesn't recompose
        assert client.delete(f"{w}/campaigns/{c['id']}", headers=h).status_code == 204
        assert client.get(f"{w}/campaigns/{c['id']}", headers=h).status_code == 404


def test_two_personas_two_grounded_pages_and_the_second_view_from_cache():
    with TestClient(app) as client:
        h, site, w = _site(client)
        c = _create(client, h, w)
        pages = {}
        for persona in ("clinic-owner", "hospital-it"):
            first = client.get(_path(site, c, persona=persona), headers=UA)
            assert first.status_code == 200, first.text
            assert 'desc="rules"' in first.headers["server-timing"]
            t0 = time.monotonic()
            second = client.get(_path(site, c, persona=persona), headers=UA)
            took = time.monotonic() - t0
            assert 'desc="cache"' in second.headers["server-timing"] and took < 1.0
            assert second.text == first.text
            pages[persona] = first.text
        a, b = pages["clinic-owner"], pages["hospital-it"]
        assert a != b
        assert "For Clinic owners" in a and "For Hospital IT" in b
        for html in (a, b):
            assert "No-shows halved in a month." in html and "apollo.svg" in html     # proof, as supplied
            assert "Sources: About Orbit" in html                                      # cited
            assert 'action="/p/' in html and "/widget/loader.js" in html             # form and agent
            assert f'data-key="{site["public_key"]}"' in html
        rows = _sql("SELECT p.persona, p.composer, p.spec FROM campaign_pages p JOIN campaigns c ON c.id = p.campaign_id "
                    "WHERE c.site_key = :s", {"s": site["site_key"]})
        assert {r["persona"] for r in rows} == {"clinic-owner", "hospital-it"}
        for r in rows:
            spec = r["spec"]
            assert spec["sections"][0]["type"] == "hero" and spec["sections"][-1]["type"] == "cta"
            for s in spec["sections"]:
                if s["type"] in ("feature_grid", "text"):
                    assert s["sources"] and all(x in spec["sources"] for x in s["sources"])

        # A question on the link is answered from the knowledge, and cached apart.
        q = client.get(_path(site, c, persona="clinic-owner", q="What does the Growth plan cost?"), headers=UA)
        assert "What does the Growth plan cost?" in q.text and "14,999" in q.text
        # The account only personalises the drawn page: no new composition.
        acct = client.get(_path(site, c, persona="clinic-owner", account="Apollo Clinics"), headers=UA)
        assert 'desc="cache"' in acct.headers["server-timing"] and "Prepared for Apollo Clinics" in acct.text
        assert 'value="Apollo Clinics"' in acct.text

        # Editing the copy composes afresh.
        client.put(f"{w}/campaigns/{c['id']}", headers=h, json={**BRIEF, "key_messages": ["Fill every slot"]})
        again = client.get(_path(site, c, persona="clinic-owner"), headers=UA)
        assert 'desc="rules"' in again.headers["server-timing"] and "Fill every slot" in again.text


def _material():
    return compose.Material(
        sources={"S1": {"text": "The Starter plan costs 4,999 rupees a month for 5 doctors.", "label": "Pricing",
                        "route": "/pricing"},
                 "S2": {"text": "Single sign-on with Azure AD.", "label": "Security", "route": None}},
        golden={"G1": {"q": "Is there a free trial?", "a": "Yes, 14 days, no card needed."}},
        blocked={"do you integrate with epic?"})


def _campaign(**over):
    base = dict(id=uuid.uuid4(), site_key="x", slug="c", name="Orbit", key_messages=["Fill every slot"],
                sections=["feature_grid", "text", "testimonials", "logos", "faq", "pricing_table", "enquiry_form"],
                cta_label="Book a demo", testimonials=[{"quote": "No-shows halved.", "name": "Dr Rao", "role": ""}],
                logos=[{"src": "https://cdn.example.com/a.svg", "alt": "A"}])
    return campaigns.Campaign(**{**base, **over})


def test_enforcement_drops_what_the_material_does_not_support():
    c, m = _campaign(), _material()
    raw = [
        {"type": "hero", "props": {"title": "Fill every slot", "subtitle": "Trusted by 10,000 clinics"}, "sources": []},
        {"type": "pricing_table", "props": {"tiers": [{"name": "Starter", "price": "₹4,999/mo"}]}, "sources": ["S1"]},
        {"type": "pricing_table", "props": {"tiers": [{"name": "Pro", "price": "₹9,999/mo"}]}, "sources": ["S1"]},
        {"type": "feature_grid", "props": {"items": [{"title": "SSO", "body": "Azure AD"}]}, "sources": []},
        {"type": "feature_grid", "props": {"items": [{"title": "SSO", "body": "Azure AD sign-on"}]}, "sources": ["S9"]},
        {"type": "text", "props": {"body": "Azure AD single sign-on."}, "sources": ["S2"]},
        {"type": "testimonials", "props": {"items": [{"quote": "Best tool ever!", "name": "Someone"}]}, "sources": []},
        {"type": "testimonials", "props": {"items": [{"quote": "no-shows  halved.", "name": "x"}]}, "sources": []},
        {"type": "logos", "props": {"items": [{"src": "https://evil.example.com/x.svg"}]}, "sources": []},
        {"type": "faq", "props": {"items": [{"q": "Do you integrate with Epic?", "a": "Yes."},
                                            {"q": "Is there a free trial?", "a": "Yes, 30 days."},
                                            {"q": "What does Starter cost?", "a": "4,999 rupees a month."}]},
         "sources": ["S1"]},
        {"type": "comparison", "props": {"columns": ["Us"], "rows": [{"label": "SSO", "values": ["yes"]}]},
         "sources": ["S2"]},
        {"type": "enquiry_form", "props": {"fields": [{"name": "card", "label": "Card number"}],
                                           "operation_id": "steal"}, "sources": []},
    ]
    out, dropped = compose.enforce(raw, c=c, m=m, arm="a")
    types = [s["type"] for s in out]
    reasons = {d["reason"] for d in dropped}
    assert types[0] == "hero" and types[-1] == "cta"                      # a hero (rebuilt) and a CTA (added)
    assert out[0]["props"]["title"] == "Fill every slot" and "10,000" not in json.dumps(out)
    assert [s["props"]["tiers"][0]["name"] for s in out if s["type"] == "pricing_table"] == ["Starter"]
    assert any(r.startswith("numbers not in its sources: 9999") for r in reasons)
    assert "cites no sources" in reasons
    assert types.count("feature_grid") == 0 and types.count("text") == 1
    assert [s["props"]["items"] for s in out if s["type"] == "testimonials"] == [[c.testimonials[0]]]
    assert "no logo the customer supplied" in reasons and "not allowed in this campaign" in reasons
    faq = next(s for s in out if s["type"] == "faq")["props"]["items"]
    assert faq == [{"q": "Is there a free trial?", "a": "Yes, 14 days, no card needed."},
                   {"q": "What does Starter cost?", "a": "4,999 rupees a month."}]
    form = next(s for s in out if s["type"] == "enquiry_form")["props"]
    assert "fields" not in form and "operation_id" not in form


def test_the_model_path_is_checked_like_the_rules():
    from app.ai.base import LLMResponse, ToolCall

    class FakeLLM:
        def __init__(self, sections):
            self.sections, self.calls = sections, []

        async def generate(self, **kw):
            self.calls.append(kw)
            return LLMResponse(tool_calls=[ToolCall(name="compose_page", args={"title": "t", "sections": self.sections})],
                               input_tokens=900, output_tokens=300)

    class Bridge:
        async def search(self, q, top_k=5):
            return [{"content": "The Starter plan costs 4,999 rupees a month for 5 doctors. Reminders cut no-shows.",
                     "score": 0.8, "document_title": "Pricing", "source_ref": {"filename": "pricing.md"}}]

    class RT:
        settings = get_settings()

        def bridge(self, db, site_key):
            return Bridge()

    good = [{"type": "hero", "props": {"title": "Fill every slot"}, "sources": ["campaign"]},
            {"type": "feature_grid", "props": {"items": [{"title": "Reminders", "body": "Reminders cut no-shows."}]},
             "sources": ["S1"]},
            {"type": "text", "props": {"body": "Starter is 4,999 rupees a month."}, "sources": ["S1"]},
            {"type": "text", "props": {"body": "Rated 4.9 by 2,000 clinics."}, "sources": ["S1"]}]

    async def run(sections):
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                llm = FakeLLM(sections)
                spec = await compose.compose(db, RT(), _campaign(site_key="model-test"), compose.Context(), llm=llm)
                return spec, llm
        finally:
            await engine.dispose()

    spec, llm = asyncio.run(run(good))
    assert spec["composer"] == "model" and spec["tokens"] == [900, 300]
    assert "SOURCES:" in llm.calls[0]["messages"][0].text and llm.calls[0]["tools"][0].name == "compose_page"
    assert "2,000" not in json.dumps(spec["sections"]) and any("4.9" in d["reason"] for d in spec["dropped"])
    assert spec["sources"]["S1"]["route"] == "/pricing"
    # A page that doesn't survive the checks falls back to the rules.
    bad = [{"type": "text", "props": {"body": "We serve 50,000 doctors."}, "sources": ["S1"]}]
    spec, _ = asyncio.run(run(bad))
    assert spec["composer"] == "rules"


def test_cache_key_parts():
    c = _campaign()
    k = dict(arm="a", persona="p", question="What is it?", lang="en", content="3:x")
    base = campaigns.cache_key(c, **k)
    assert campaigns.cache_key(c, **{**k, "question": "  what IS it? "}) == base
    for change in ({"arm": "b"}, {"persona": "q"}, {"question": "Other?"}, {"lang": "hi"}, {"content": "4:y"}):
        assert campaigns.cache_key(c, **{**k, **change}) != base, change
    c.version += 1
    assert campaigns.cache_key(c, **k) != base


def test_conversions_engagement_analytics_and_a_variant():
    with TestClient(app) as client:
        h, site, w = _site(client)
        c = _create(client, h, w, variant={"headline": "Never lose a booking again", "cta_label": "See it live"})
        arms = {}
        for i in range(12):
            client.cookies.clear()
            r = client.get(_path(site, c, persona="clinic-owner", utm_source="google"), headers=UA)
            arms.setdefault("b" if "Never lose a booking again" in r.text else "a", []).append(
                r.cookies.get("fb_pv") or client.cookies.get("fb_pv"))
        assert set(arms) == {"a", "b"}, "both arms are served"
        viewer = arms["b"][0]
        client.cookies.clear()
        client.cookies.set("fb_pv", viewer, path="/p")
        assert "Never lose a booking again" in client.get(_path(site, c), headers=UA).text  # sticky arm
        # Engagement (once per half hour), the CTA, and the form.
        for _ in range(3):
            assert client.post(_path(site, c) + "/event", content=json.dumps({"kind": "engage"}),
                               headers={**UA, "Content-Type": "text/plain"}).status_code == 204
        go = client.get(_path(site, c) + "/go", headers=UA, follow_redirects=False)
        assert go.status_code == 302 and go.headers["location"] == BRIEF["cta_url"]
        form = client.post(_path(site, c) + "/lead", headers=UA, follow_redirects=False,
                           data={"email": "ops@apollo.example.com", "name": "Asha", "company": "Apollo",
                                 "persona": "clinic-owner", "utm_source": "google"})
        assert form.status_code == 303 and "sent=1" in form.headers["location"]
        assert "the team will be in touch" in client.get(form.headers["location"].split("#")[0], headers=UA).text
        lead = _sql("SELECT source, persona, interest FROM leads WHERE site_key = :s", {"s": site["site_key"]})[0]
        assert lead["source"] == "campaign" and lead["persona"] == "clinic-owner" and "Orbit for healthcare" in lead["interest"]
        # Spam: the hidden field is ignored quietly.
        client.post(_path(site, c) + "/lead", headers=UA, data={"email": "bot@spam.example.com", "website": "x"})
        assert len(_sql("SELECT 1 FROM leads WHERE site_key = :s", {"s": site["site_key"]})) == 1
        # Bots aren't counted.
        client.get(_path(site, c), headers={"User-Agent": "Slackbot-LinkExpanding 1.0"})

        a = client.get(f"{w}/campaigns/{c['id']}/analytics", headers=h).json()
        assert a["total"]["views"] == 12 and a["total"]["engaged"] == 1 and a["total"]["converted"] == 1
        assert {r["arm"] for r in a["by_arm"]} == {"a", "b"}
        assert next(r for r in a["by_arm"] if r["arm"] == "b")["converted"] == 1
        assert a["by_source"][0]["source"] == "google"
        assert a["cache"]["served_from_cache"] >= 10 and a["cache"]["pages"] == 3
        assert a["experiment"]["status"] in ("keep_running", "winner", "no_difference")
        listed = client.get(f"{w}/campaigns", headers=h).json()["campaigns"][0]
        assert listed["views_30d"] == 12 and listed["conversions_30d"] == 1


def test_drafts_previews_embeds_and_site_deletion():
    with TestClient(app) as client:
        h, site, w = _site(client, domain="orbit.example.com")
        c = _create(client, h, w, status="draft", embed_origins=["https://partner.example.org/page"])
        assert client.get(_path(site, c), headers=UA).status_code == 404
        assert client.get(_path(site, c, preview="nope"), headers=UA).status_code == 404
        token = c["preview_url"].split("preview=")[1]
        pv = client.get(_path(site, c, preview=token, arm="a"), headers=UA)
        assert pv.status_code == 200 and "Preview" in pv.text and "/widget/loader.js" not in pv.text
        assert not _sql("SELECT 1 FROM campaign_events e JOIN campaigns c ON c.id = e.campaign_id "
                        "WHERE c.site_key = :s", {"s": site["site_key"]})
        assert client.post(_path(site, c) + "/lead", data={"email": "a@b.example.com"}).status_code == 404

        client.put(f"{w}/campaigns/{c['id']}", headers=h, json={**BRIEF, "status": "live",
                                                                "embed_origins": ["https://partner.example.org"]})
        normal = client.get(_path(site, c), headers=UA)
        assert "frame-ancestors 'none'" in normal.headers["content-security-policy"]
        csp = client.get(_path(site, c, embed="1"), headers=UA).headers["content-security-policy"]
        assert "frame-ancestors https://partner.example.org https://orbit.example.com https://*.orbit.example.com" in csp
        assert "script-src" in csp and "form-action 'self'" in csp
        assert client.get(f"/p/{site['site_key']}/nope", headers=UA).status_code == 404

        assert client.delete(w, headers=h).status_code == 204
        assert not _sql("SELECT 1 FROM campaigns WHERE site_key = :s", {"s": site["site_key"]})
