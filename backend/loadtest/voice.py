"""
Load test for the voice path (M3-6): many widget sessions at once over
``/ws/voice``, each asking a few questions, measuring what a visitor feels.

    python -m loadtest.voice --url ws://localhost:8081/ws/voice --key fbk_… \\
        --sessions 50 --turns 3 --ramp 10 [--think 1.0] [--json out.json]

Per turn: time to first audio (the ack — what the visitor hears first), time to
the first audio of the answer itself (the second segment), and the whole turn
(question sent → the answer's last audio). Also: connection failures, turns
that errored or timed out, and drains (1012/1013) seen. Exits non-zero if any
turn failed or ``--max-p95-ttfa`` is exceeded, so it can gate a release.

Run it against a staging replica with the same settings as production (in
MOCK_AI mode it measures the platform's own overhead: transport, routing,
retrieval, TTS framing — not the model's latency).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

SETTLE_S = 0.8
QUESTIONS = (
    "What do you do?", "How much does it cost?", "Do you integrate with Salesforce?",
    "Is there a free trial?", "How do I get started?", "Do you support single sign-on?",
    "Where is my data stored?", "Can I talk to someone?",
)


class RateLimited(Exception):
    """The site's public rate limit refused the turn (protection, not a failure)."""


@dataclass
class Result:
    connected: int = 0
    connect_failed: int = 0
    turns: int = 0
    failed: int = 0
    drained: int = 0
    rate_limited: int = 0
    ttfa: list[float] = field(default_factory=list)
    answer_audio: list[float] = field(default_factory=list)
    turn: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return round(xs[k], 4)


def summary(r: Result, wall_s: float) -> dict[str, Any]:
    def stats(xs: list[float]) -> dict[str, Any]:
        return {"p50": _pct(xs, 50), "p95": _pct(xs, 95), "p99": _pct(xs, 99),
                "mean": round(statistics.fmean(xs), 4) if xs else None, "n": len(xs)}
    return {"sessions_connected": r.connected, "connect_failed": r.connect_failed, "turns": r.turns,
            "turns_failed": r.failed, "drained": r.drained, "rate_limited": r.rate_limited,
            **({"note": "turns were refused by the site's public rate limit: raise PUBLIC_RATE_LIMIT_PER_MIN "
                        "on the target to measure capacity"} if r.rate_limited else {}),
            "wall_seconds": round(wall_s, 2),
            "turns_per_second": round(r.turns / wall_s, 2) if wall_s else None,
            "time_to_first_audio_s": stats(r.ttfa), "time_to_answer_audio_s": stats(r.answer_audio),
            "turn_s": stats(r.turn), "errors": r.errors[:20]}


async def _turn(ws: Any, question: str, timeout: float) -> tuple[float, Optional[float], float]:
    """Send one question; return (ttfa, answer audio, whole turn) in seconds."""
    t0 = time.perf_counter()
    await ws.send(json.dumps({"channel": "EVENTS", "type": "text", "payload": {"text": question}}))
    first: Optional[float] = None
    starts = 0
    answer: Optional[float] = None
    last_end: Optional[float] = None
    deadline = t0 + timeout
    while True:
        left = deadline - time.perf_counter()
        if left <= 0:
            raise TimeoutError(f"no answer in {timeout:.0f} s")
        try:
            # After an answer segment ends, a quiet pause means the turn is over
            # (a long answer streams several segments).
            msg = await asyncio.wait_for(ws.recv(), min(left, SETTLE_S) if last_end else left)
        except asyncio.TimeoutError:
            if last_end is not None:
                return first or 0.0, answer, last_end
            raise
        if isinstance(msg, (bytes, bytearray)):         # a binary TTS frame
            if first is None:
                first = time.perf_counter() - t0
            continue
        env = json.loads(msg)
        ch, ty = env.get("channel"), env.get("type")
        if ch == "AUDIO" and ty == "start":
            starts += 1
            if first is None:
                first = time.perf_counter() - t0
            if starts == 2 and answer is None:
                answer = time.perf_counter() - t0
        elif ch == "AUDIO" and ty == "end" and starts >= 2:
            last_end = time.perf_counter() - t0
        elif ch == "EVENTS" and ty == "error":
            if (env.get("payload") or {}).get("reason") == "rate_limited":
                raise RateLimited()
            raise RuntimeError(f"server error: {env.get('payload')}")


async def _session(n: int, url: str, turns: int, think: float, timeout: float, r: Result) -> None:
    import websockets

    try:
        ws = await websockets.connect(url, open_timeout=timeout, max_size=None)
    except Exception as exc:
        r.connect_failed += 1
        r.errors.append(f"connect {n}: {type(exc).__name__}: {exc}"[:200])
        return
    try:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if ready.get("type") != "ready":
            raise RuntimeError(f"expected ready, got {ready.get('type')}")
        r.connected += 1
        for i in range(turns):
            q = random.choice(QUESTIONS)
            try:
                ttfa, answer, whole = await _turn(ws, q, timeout)
                r.turns += 1
                r.ttfa.append(ttfa)
                r.turn.append(whole)
                if answer is not None:
                    r.answer_audio.append(answer)
            except RateLimited:
                r.rate_limited += 1
                continue
            except Exception as exc:
                code = getattr(exc, "code", None) or getattr(getattr(exc, "rcvd", None), "code", None)
                if code in (1012, 1013):
                    r.drained += 1
                    return
                r.failed += 1
                r.errors.append(f"session {n} turn {i}: {type(exc).__name__}: {exc}"[:200])
                return
            if think:
                await asyncio.sleep(random.uniform(0.5, 1.5) * think)
    except Exception as exc:
        r.failed += 1
        r.errors.append(f"session {n}: {type(exc).__name__}: {exc}"[:200])
    finally:
        await ws.close()


async def run(url: str, *, sessions: int, turns: int, ramp: float = 0.0, think: float = 0.0,
              timeout: float = 30.0) -> dict[str, Any]:
    r = Result()
    t0 = time.perf_counter()

    async def start(i: int) -> None:
        if ramp and sessions > 1:
            await asyncio.sleep(ramp * i / (sessions - 1))
        await _session(i, url, turns, think, timeout, r)

    await asyncio.gather(*(start(i) for i in range(sessions)))
    return summary(r, time.perf_counter() - t0)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="ws://localhost:8080/ws/voice")
    p.add_argument("--key", default="", help="a site's widget key (fbk_…)")
    p.add_argument("--site", default="", help="or a demo site key, e.g. hirebuddha")
    p.add_argument("--sessions", type=int, default=20)
    p.add_argument("--turns", type=int, default=3)
    p.add_argument("--ramp", type=float, default=5.0, help="seconds over which sessions start")
    p.add_argument("--think", type=float, default=1.0, help="mean pause between a session's questions (s)")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--max-p95-ttfa", type=float, default=0.0, help="fail if p95 time to first audio is above this (s)")
    p.add_argument("--json", default="", help="also write the summary here")
    a = p.parse_args()
    sep = "&" if "?" in a.url else "?"
    url = a.url + (f"{sep}key={a.key}" if a.key else f"{sep}site={a.site}" if a.site else "") + "&audio=binary"
    out = asyncio.run(run(url, sessions=a.sessions, turns=a.turns, ramp=a.ramp, think=a.think, timeout=a.timeout))
    text = json.dumps(out, indent=2)
    print(text)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(text)
    p95 = out["time_to_first_audio_s"]["p95"]
    bad = out["turns_failed"] or out["connect_failed"] or (a.max_p95_ttfa and p95 is not None and p95 > a.max_p95_ttfa)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
