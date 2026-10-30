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
