"""
Readiness of every dependency (M3-6), for ``/readyz``, the status page and
the ``fb_ready`` gauge Prometheus alerts on.

Critical — this replica can't serve without them, so ``/readyz`` is 503:

* ``db``          a query answers;
* ``migrations``  the schema is at this version's head revision;
* ``redis``       answers (only when ``REDIS_URL`` is set: sessions and rate
                  limits live there);
* ``draining``    the replica is shutting down (it says so on purpose).

Reported but not critical (``degraded``):

* ``scheduler``   the periodic jobs loop is alive;
* ``models``      the AI provider is configured and recent calls aren't failing;
* ``email``       SMTP is configured and the outbox isn't backing up.

Each check has a 2-second timeout and they run together.
"""
from __future__ import annotations

import asyncio
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable

from sqlalchemy import text

from app.config import get_settings

TIMEOUT_S = 2.0
_ENGINE_ERRORS_WINDOW_S = 300
_engine_errors: dict[str, Any] = {"at": 0.0, "count": 0.0, "recent": 0.0}


@lru_cache
def head_revision() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head() or ""


async def _db() -> dict:
    from app.db import engine
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"ok": True}


async def _migrations() -> dict:
    from app.db import engine
    async with engine.connect() as conn:
        current = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    head = head_revision()
    return {"ok": current == head, "detail": current if current == head else f"at {current}, expected {head}"}


async def _redis() -> dict:
    url = get_settings().redis_url
    if not url:
        return {"ok": True, "detail": "not used"}
    import redis.asyncio as aioredis
    client = aioredis.from_url(url)
    try:
        await client.ping()
    finally:
        await client.aclose()
    return {"ok": True}


async def _scheduler(app: Any) -> dict:
    sched = getattr(getattr(app, "state", None), "scheduler", None)
    if sched is None:
        return {"ok": False, "detail": "not started"}
    tasks = getattr(sched, "_tasks", [])
    if not getattr(sched, "jobs", None):
        return {"ok": True, "detail": "no jobs configured"}
    dead = [t.get_name() for t in tasks if t.done()]
    return {"ok": bool(tasks) and not dead, "detail": ("stopped: " + ", ".join(dead)) if dead else None}


def _recent_engine_errors() -> float:
    from app.observability.metrics import ENGINE_ERRORS
    total = sum(s.value for m in ENGINE_ERRORS.collect() for s in m.samples if s.name.endswith("_total"))
    now = time.monotonic()
    if now - _engine_errors["at"] > _ENGINE_ERRORS_WINDOW_S:
        _engine_errors.update(recent=total - _engine_errors["count"], count=total, at=now)
    return float(_engine_errors["recent"])


async def _models(app: Any) -> dict:
    s = get_settings()
    if s.mock_ai:
        return {"ok": True, "detail": "mock"}
    configured = bool(s.google_cloud_project)
    errors = _recent_engine_errors()
    ok = configured and errors < 20
    detail = None if ok else ("no Google Cloud project configured" if not configured
                              else f"{int(errors)} model errors in 5 minutes")
    return {"ok": ok, "detail": detail}


async def _email() -> dict:
    s = get_settings()
    if not s.smtp_host:
        return {"ok": True, "detail": "not configured"}
    from app.db import engine
    async with engine.connect() as conn:
        backlog = (await conn.execute(text(
            "SELECT count(*) FROM email_outbox WHERE status IN ('queued', 'sending') AND created_at < now() - interval '15 minutes'"
        ))).scalar() or 0
    return {"ok": backlog < 50, "detail": f"{backlog} emails waiting over 15 minutes" if backlog else None}


async def _timed(fn: Callable[[], Awaitable[dict]]) -> dict:
    t0 = time.perf_counter()
    try:
        out = await asyncio.wait_for(fn(), TIMEOUT_S)
    except asyncio.TimeoutError:
        out = {"ok": False, "detail": f"no answer in {TIMEOUT_S:.0f} s"}
    except Exception as exc:
        out = {"ok": False, "detail": type(exc).__name__ + (f": {exc}"[:160] if str(exc) else "")}
    out["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


CRITICAL = ("db", "migrations", "redis")


# The running app, set at startup, so the jobs' probe sees its scheduler.
current_app: Any = None


async def check_all(app: Any = None) -> dict[str, Any]:
    from app.observability import metrics
    from app.transport import drain

    app = app or current_app
    names = ("db", "migrations", "redis", "scheduler", "models", "email")
    fns = (_db, _migrations, _redis, lambda: _scheduler(app), lambda: _models(app), _email)
    results = await asyncio.gather(*(_timed(f) for f in fns))
    checks = {n: {**r, "critical": n in CRITICAL} for n, r in zip(names, results)}
    checks["draining"] = {"ok": not drain.draining(), "critical": True, "ms": 0.0,
                          "detail": f"shutting down; {drain.open_sessions()} voice session(s) moving" if drain.draining() else None}
    for n, c in checks.items():
        metrics.READY.labels(n).set(1 if c["ok"] else 0)
    if drain.draining():
        status = "draining"
    elif any(not c["ok"] for c in checks.values() if c["critical"]):
        status = "fail"
    elif any(not c["ok"] for c in checks.values()):
        status = "degraded"
    else:
        status = "ok"
    return {"status": status, "checks": checks}
