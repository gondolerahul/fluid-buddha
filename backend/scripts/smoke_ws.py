"""Exercise the multiplexed WebSocket voice transport via TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def drain_turn(ws, max_msgs: int = 200) -> None:
    audio_ends = 0
    chunk_counts: dict[str, int] = {}
    while audio_ends < 2 and max_msgs > 0:
        env = ws.receive_json()
        max_msgs -= 1
        ch, ty, sid = env["channel"], env["type"], env.get("sync_id")
        if ch == "AUDIO" and ty == "chunk":
            chunk_counts[sid] = chunk_counts.get(sid, 0) + 1
            continue
        if ch == "AUDIO" and ty == "end":
            audio_ends += 1
            print(f"  AUDIO/end   sync={sid}  ({chunk_counts.get(sid,0)} pcm chunks)")
            continue
        extra = ""
        if ch == "DATA":
            extra = f"  component={env['payload'].get('component_type')}"
        elif ch == "EVENTS" and ty in ("navigate", "set_persona", "scroll_to"):
            extra = f"  {env['payload']}"
        elif ch == "AUDIO" and ty == "start":
            extra = f"  text={env['payload'].get('text','')[:48]!r}"
        elif ch == "STATE" and ty == "transcript":
            extra = f"  {env['payload'].get('text')!r}"
        print(f"  {ch}/{ty:10} sync={sid}{extra}")


def main() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/voice?site=hirebuddha") as ws:
            ready = ws.receive_json()
            print("READY:", ready["channel"], ready["type"], ready["payload"]["config"])
            for text in ["How does pricing and ROI work for a growing company?",
                         "How do you integrate with our API?"]:
                print(f"\n>>> USER: {text}")
                ws.send_json({"channel": "EVENTS", "type": "text",
                              "payload": {"text": text}})
                drain_turn(ws)


if __name__ == "__main__":
    main()
