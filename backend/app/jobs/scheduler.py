"""
Periodic background jobs (M2-0).

One small in-process scheduler instead of a loop per feature. Each job runs
every ``interval_s`` seconds (first run after one interval, unless
``run_at_start``), and holds a Postgres advisory lock while it runs, so with
several replicas only one runs a given job at a time. Jobs must still be
idempotent: replicas take turns, they don't coordinate schedules.

A failing run is logged and counted; the loop carries on.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    name: str
    interval_s: float
    run: Callable[[], Awaitable[object]]
    run_at_start: bool = False


def lock_key(name: str) -> int:
    """A stable signed 64-bit advisory-lock key per job name."""
    return int.from_bytes(hashlib.sha256(f"fb-job:{name}".encode()).digest()[:8], "big",
                          signed=True)


async def run_locked(job: Job, engine=None) -> bool:
    """Run ``job`` once if no other replica is running it. True when it ran."""
    from app.observability.metrics import JOB_RUNS

    if engine is None:
        from app.db import engine
    async with engine.connect() as conn:
        got = (await conn.execute(text("SELECT pg_try_advisory_lock(:k)"),
                                  {"k": lock_key(job.name)})).scalar()
        await conn.commit()
        if not got:
            JOB_RUNS.labels(job.name, "skipped").inc()
            return False
        try:
            result = await job.run()
            JOB_RUNS.labels(job.name, "ok").inc()
            if result:
                logger.info("job %s: %s", job.name, result)
            return True
        except Exception:
            JOB_RUNS.labels(job.name, "error").inc()
            logger.exception("job %s failed", job.name)
            return True
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key(job.name)})
            await conn.commit()


async def _loop(job: Job) -> None:
    if not job.run_at_start:
        await asyncio.sleep(job.interval_s)
    while True:
        try:
            await run_locked(job)
        except Exception:   # e.g. the database is briefly unreachable
            logger.exception("job %s: could not run", job.name)
        await asyncio.sleep(job.interval_s)


class Scheduler:
    def __init__(self) -> None:
        self.jobs: list[Job] = []
        self._tasks: list[asyncio.Task] = []

    def add(self, job: Job) -> None:
        if job.interval_s > 0:
            self.jobs.append(job)

    def start(self) -> None:
        self._tasks = [asyncio.create_task(_loop(j), name=f"job:{j.name}") for j in self.jobs]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
