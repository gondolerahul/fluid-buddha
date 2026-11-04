"""
The live event bus (M2-2): how a visitor's socket and the operators' consoles
reach each other, on whichever backend replica each is connected to.

Topics:
* ``session:{site_key}:{session_id}`` — for one visitor: a person joined or
  left, their messages, call signals;
* ``site:{site_key}`` — for operators watching a site: visitors arriving and
  leaving, every question and answer, takeovers, call signals.

Without ``REDIS_URL`` events fan out inside this process (one replica). With
it, they're published to Redis and one subscriber task per process relays
them to the local listeners, so a visitor on replica A and an operator on
replica B still talk. Delivery is best effort and in order per publisher —
the durable record is in the database (``live_messages``).
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)

_PREFIX = "fb:live:"
_QUEUE_MAX = 256


def session_topic(site_key: str, session_id: str) -> str:
    return f"session:{site_key}:{session_id}"


def site_topic(site_key: str) -> str:
    return f"site:{site_key}"


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._relay: asyncio.Task | None = None

    def _local(self, topic: str, event: dict) -> None:
        for q in list(self._subs.get(topic, ())):
            try:
                q.put_nowait((topic, event))
            except asyncio.QueueFull:   # a stuck listener loses events, not the bus
                logger.warning("live bus: listener on %s is full; event dropped", topic)

    async def publish(self, topic: str, event: dict) -> None:
        from app.shared_state import redis_client

        client = redis_client()
        if client is not None:
            try:
                await client.publish(_PREFIX + topic, json.dumps(event, default=str))
                return
            except Exception as exc:   # Redis down: at least this replica hears it
                logger.warning("live bus: Redis publish failed (%s); local only", exc)
        self._local(topic, event)

    async def _ensure_relay(self) -> None:
        from app.shared_state import redis_client

        client = redis_client()
        if client is None or (self._relay and not self._relay.done()):
            return

        async def relay() -> None:
            while True:
                try:
                    pubsub = client.pubsub()
                    await pubsub.psubscribe(_PREFIX + "*")
                    async for msg in pubsub.listen():
                        if msg.get("type") != "pmessage":
                            continue
                        topic = str(msg["channel"])[len(_PREFIX):]
                        try:
                            self._local(topic, json.loads(msg["data"]))
                        except ValueError:
                            continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("live bus: Redis subscription lost (%s); retrying", exc)
                    await asyncio.sleep(1.0)

        self._relay = asyncio.create_task(relay(), name="live-bus-relay")

    @asynccontextmanager
    async def subscribe(self, *topics: str) -> AsyncIterator[asyncio.Queue]:
        """A queue receiving ``(topic, event)`` for every event published on
        ``topics`` while open."""
        await self._ensure_relay()
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAX)
        for t in topics:
            self._subs.setdefault(t, set()).add(q)
        try:
            yield q
        finally:
            for t in topics:
                subs = self._subs.get(t)
                if subs is not None:
                    subs.discard(q)
                    if not subs:
                        self._subs.pop(t, None)


bus = Bus()
