"""
Admin tour view/edit tests (Phase 4, req D).

    MOCK_AI=true python -m pytest tests/test_tour_admin.py -q
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _tenant(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"tour_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_tour_get_put_and_generate():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid = client.post("/tenant/websites", json={"name": "Tour Co"}, headers=h).json()["id"]

        assert client.get(f"/tenant/websites/{wid}/tour", headers=h).json()["exists"] is False

        payload = {"stops": [
            {"narration": "Welcome — quick tour.", "move": {"type": "scroll", "target": "down"}},
            {"narration": "Our pricing.", "move": {"type": "navigate", "route": "/pricing"}},
            {"narration": "Thanks for visiting!", "label": "use-case"},
        ]}
        assert client.put(f"/tenant/websites/{wid}/tour", json=payload, headers=h).status_code == 200
        reloaded = client.get(f"/tenant/websites/{wid}/tour", headers=h).json()
        assert reloaded["exists"] and len(reloaded["stops"]) == 3
        assert reloaded["stops"][0]["move"]["target"] == "down"

        # empty plan rejected; generate before ingest is a conflict
        assert client.put(f"/tenant/websites/{wid}/tour", json={"stops": []},
                          headers=h).status_code == 422
        assert client.post(f"/tenant/websites/{wid}/tour/generate", headers=h).status_code == 409

        # after ingesting content, generate authors a usable plan
        client.post(f"/tenant/websites/{wid}/sources", json={
            "kind": "text", "name": "Home",
            "content": "[Page: /]\n\nWelcome to Tour Co. We sell premium widgets, 24/7 support.",
        }, headers=h)
        client.post(f"/tenant/websites/{wid}/ingestion/run?wait=true", headers=h)
        gen = client.post(f"/tenant/websites/{wid}/tour/generate", headers=h)
        assert gen.status_code == 200 and len(gen.json()["stops"]) >= 2
