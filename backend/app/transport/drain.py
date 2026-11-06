"""
Graceful shutdown for voice sessions (M3-6).

On SIGTERM (a deploy, a scale-down, ``docker compose stop``) the replica:

1. turns ``/readyz`` to 503 (``draining``) so the load balancer stops sending
   new visitors;
2. tells every open voice session to move (``EVENTS/reconnect``), lets each
   finish the answer it is speaking, then closes it with 1012 ("service
   restart"); the widget reconnects quietly, to a healthy replica;
3. refuses new sockets with 1013 ("try again later") meanwhile;
4. after ``DRAIN_SECONDS`` closes whatever is left, so the process exits
   inside the orchestrator's grace period (uvicorn's
   ``--timeout-graceful-shutdown`` and Compose's ``stop_grace_period`` are set
   above it).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

SERVICE_RESTART = 1012
TRY_AGAIN_LATER = 1013

_sessions: set[Any] = set()
_state: dict[str, Any] = {"draining": False, "since": None, "task": None}


def register(session: Any) -> None:
    _sessions.add(session)


def unregister(session: Any) -> None:
    _sessions.discard(session)


def draining() -> bool:
    return bool(_state["draining"])


def open_sessions() -> int:
    return len(_sessions)


def reset() -> None:
    """Back to serving (tests)."""
    from app.observability.metrics import DRAINING
    DRAINING.set(0)
    _state.update(draining=False, since=None, task=None)


async def drain(timeout: float = 30.0) -> dict[str, int]:
    """Move every voice session off this replica. Returns what happened."""
    if not _state["draining"]:
        from app.observability.metrics import DRAINING
        DRAINING.set(1)
        _state.update(draining=True, since=time.time())
        logger.info("draining: %d voice session(s) open", len(_sessions))
    sessions = list(_sessions)
    results = await asyncio.gather(*(s.drain(timeout) for s in sessions), return_exceptions=True)
    forced = sum(1 for r in results if r is True)
    out = {"sessions": len(sessions), "forced": forced, "left": len(_sessions)}
    logger.info("drained: %s", out)
    return out


def start(timeout: float) -> None:
    """Begin draining in the background (from a signal handler)."""
    if _state["task"] is None:
        _state["task"] = asyncio.get_running_loop().create_task(drain(timeout))


def install_signal_hook(timeout: float) -> None:
    """Drain on SIGTERM/SIGINT, then let the server's own handler stop it.

    Uvicorn installs its handlers before the app starts; chaining keeps its
    shutdown (stop accepting, wait for connections) while the sessions move.
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            previous = signal.getsignal(sig)
        except (ValueError, AttributeError):
            continue

        def handler(signum: int, frame: Any, _previous: Any = previous) -> None:
            loop.call_soon_threadsafe(start, timeout)
            if callable(_previous):
                _previous(signum, frame)

        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):   # not the main thread (tests), or unsupported
            pass


async def wait_for_turn(task: Optional[asyncio.Task], timeout: float) -> bool:
    """Let a response that is being spoken finish. True if it had to be cut."""
    if task is None or task.done():
        return False
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout)
        return False
    except (asyncio.TimeoutError, asyncio.CancelledError):
        return True
    except Exception:
        return False
