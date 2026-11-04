"""
Multiplexed message envelope (Req 3.2.2 / §5.1).

A single WebSocket carries JSON envelopes tagged with a logical ``channel`` and a
``type``. Correlated audio + UI for the same explanation share a ``sync_id`` so
the frontend jitter buffer can hold audio until its UI has rendered.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from pydantic import BaseModel, Field


# Logical channels
class Channel:
    AUDIO = "AUDIO"      # streaming ASR (in) / TTS (out)
    DATA = "DATA"        # dynamic UI component payloads + patches
    EVENTS = "EVENTS"    # DOM commands: navigate / scroll_to / set_persona / ack
    STATE = "STATE"      # frontend->backend: viewport, transcript, barge-in


def now_ms() -> int:
    return int(time.time() * 1000)


class Envelope(BaseModel):
    channel: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sync_id: Optional[str] = None
    timestamp: int = Field(default_factory=now_ms)


def make(channel: str, type_: str, payload: dict[str, Any] | None = None,
         sync_id: str | None = None) -> dict[str, Any]:
    """Build an outgoing envelope dict ready for ``ws.send_json``."""
    return Envelope(
        channel=channel, type=type_, payload=payload or {}, sync_id=sync_id
    ).model_dump()


# ---------------------------------------------------------------------------
# Binary audio frames (WS5). Audio is the bulk of the traffic, so a client that
# opts in (``/ws/voice?audio=binary``) gets TTS chunks as binary WebSocket
# frames instead of base64 inside JSON (a third smaller, no JSON parse), and
# may send its mic chunks the same way. Layout:
#
#   byte 0       frame kind (AUDIO_CHUNK)
#   byte 1       length N of the sync_id (0-255)
#   bytes 2..N+1 sync_id, ASCII
#   rest         PCM16 little-endian mono
# ---------------------------------------------------------------------------

AUDIO_CHUNK = 0x01


def pack_audio(sync_id: str | None, pcm: bytes) -> bytes:
    sid = (sync_id or "").encode("ascii", "ignore")[:255]
    return bytes((AUDIO_CHUNK, len(sid))) + sid + pcm


def unpack_audio(frame: bytes) -> tuple[str, bytes] | None:
    """``(sync_id, pcm)`` for an audio frame, or None for anything else."""
    if len(frame) < 2 or frame[0] != AUDIO_CHUNK:
        return None
    n = frame[1]
    if len(frame) < 2 + n:
        return None
    return frame[2:2 + n].decode("ascii", "ignore"), bytes(frame[2 + n:])
