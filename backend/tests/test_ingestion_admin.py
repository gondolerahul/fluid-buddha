"""
Admin ingestion-control tests (Phase 3, req C). Mock mode + pgvector:

    MOCK_AI=true python -m pytest tests/test_ingestion_admin.py -q

Covers adding a text source + an uploaded file, a synchronous ingestion run that
creates CORTEX nodes, status transitions, deletion, and tenant isolation.
"""
from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient


def _tenant(client: TestClient) -> dict:
    email = f"ing_{uuid.uuid4().hex[:10]}@example.com"
    tok = client.post("/auth/register",
                      json={"email": email, "password": "supersecret1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_ingestion_flow_and_isolation():
    from app.main import app

    with TestClient(app) as client:
        h = _tenant(client)
        wid = client.post("/tenant/websites", json={"name": "Ingest Co"}, headers=h).json()["id"]

        # add a pasted-text source + an uploaded file
        assert client.post(f"/tenant/websites/{wid}/sources", json={
            "kind": "text", "name": "Pricing",
            "content": "Our Pro plan costs $49/month with voice minutes included.",
        }, headers=h).status_code == 201
        files = {"file": ("faq.md", io.BytesIO(b"# FAQ\nRefunds within 30 days."), "text/markdown")}
        assert client.post(f"/tenant/websites/{wid}/sources/upload",
                           files=files, headers=h).status_code == 201

        before = client.get(f"/tenant/websites/{wid}/ingestion", headers=h).json()
        assert before["counts"]["pending"] == 2 and before["document_count"] == 0

        run = client.post(f"/tenant/websites/{wid}/ingestion/run?wait=true", headers=h).json()
        assert run["status"] == "done" and run["ingested"] == 2 and run["nodes"] > 0

        after = client.get(f"/tenant/websites/{wid}/ingestion", headers=h).json()
        assert after["counts"]["ingested"] == 2 and after["document_count"] == 2

        sid = after["sources"][0]["id"]
        assert client.delete(f"/tenant/websites/{wid}/sources/{sid}", headers=h).status_code == 204

        # another tenant cannot reach this site's ingestion
        h2 = _tenant(client)
        assert client.get(f"/tenant/websites/{wid}/ingestion", headers=h2).status_code == 404
