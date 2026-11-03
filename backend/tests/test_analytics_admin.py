"""
Cost/performance analytics tests (Phase 6, req F/G).

    MOCK_AI=true python -m pytest tests/test_analytics_admin.py -q

Drives generated + cached /chat turns, then asserts the analytics endpoint
returns a category cost breakdown, day/hour/session groupings, performance
percentiles, and the generated-vs-cached split.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.analytics.pricing import get_pricing


def test_pricing_cost_math():
    p = get_pricing()
    # 60s of ASR == one minute's rate; 1000 TTS chars == the per-1k rate.
    assert abs(p.cost_asr(60_000) - p.asr_per_min) < 1e-9
    assert abs(p.cost_tts(1000) - p.tts_per_1k_chars) < 1e-9
    assert p.cost_thinker(1000, 1000) > 0


def test_analytics_breakdown_and_cache_split():
    from app.main import app

    with TestClient(app) as client:
        tok = client.post("/auth/register", json={
            "email": f"an_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        site = client.post("/tenant/websites", json={"name": "Analytics Co"}, headers=h).json()
        wid, key = site["id"], site["public_key"]

        # Make a repeated question replay from cache after one prior turn.
        app.state.runtime.settings.episodic_min_episodes = 1

        # Drive the public path with the widget key (a registered tenant site
        # can no longer be reached by raw site_key — docs/defects.md D-1).
        for m in ["Tell me about your product",
                  "What does pricing look like for a startup?",
                  "Show me an integration diagram",
                  "How do I get started today?"]:
            client.post("/chat", json={"message": m, "key": key})
        cached = client.post("/chat", json={"message": "Tell me about your product", "key": key}).json()
        assert cached["intent"] == "cached"

        a = client.get(f"/tenant/websites/{wid}/analytics?group_by=day", headers=h).json()
        totals = a["totals"]
        assert totals["turns"] == 5
        assert totals["generated_turns"] == 4 and totals["cached_turns"] == 1
        # generated turns spent LLM tokens -> non-zero cost; cached spent none
        assert totals["total_cost"] > 0
        assert a["cache_split"]["cached"]["cost"] == 0.0
        assert a["cache_split"]["generated"]["cost"] > 0
        # category keys present
        for k in ("asr_cost", "tts_cost", "fast_llm_cost", "thinker_llm_cost", "tool_cost"):
            assert k in totals
        # performance
        assert a["performance"]["cache_hit_rate"] == 0.2
        assert "p95_latency_ms" in a["performance"]

        # all groupings work; session grouping yields one bucket per session
        assert len(client.get(f"/tenant/websites/{wid}/analytics?group_by=hour",
                              headers=h).json()["series"]) >= 1
        assert len(client.get(f"/tenant/websites/{wid}/analytics?group_by=session",
                              headers=h).json()["series"]) == 5
        assert client.get(f"/tenant/websites/{wid}/analytics?group_by=bogus",
                          headers=h).status_code == 422

        # isolation
        t2 = client.post("/auth/register", json={
            "email": f"o_{uuid.uuid4().hex[:8]}@example.com", "password": "supersecret1",
        }).json()["access_token"]
        assert client.get(f"/tenant/websites/{wid}/analytics",
                          headers={"Authorization": f"Bearer {t2}"}).status_code == 404
