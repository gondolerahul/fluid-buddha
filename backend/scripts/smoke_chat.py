"""Boot the app (runs lifespan -> schema + runtime) and exercise /chat."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    with TestClient(app) as client:
        print("== /readyz ==")
        print(json.dumps(client.get("/readyz").json(), indent=2))

        sid = None
        for msg in [
            "Hi there!",
            "How does the ROI and pricing work for a growing company?",
            "How do you integrate with our existing API stack?",
            "Tell me about security and compliance for enterprise.",
        ]:
            body = {"message": msg}
            if sid:
                body["session_id"] = sid
            r = client.post("/chat", json=body).json()
            sid = r.get("session_id", sid)
            print(f"\n== USER: {msg}")
            print("  ack      :", r["ack"])
            print("  intent   :", r["intent"], "| persona:", r["persona"])
            print("  grounding:", r["grounding"]["found"],
                  round(r["grounding"]["confidence"], 3))
            print("  actions  :", r["actions"])
            print("  comps    :", [c["component_type"] for c in r["components"]])
            print("  answer   :", (r["text"] or "")[:160])


if __name__ == "__main__":
    main()
