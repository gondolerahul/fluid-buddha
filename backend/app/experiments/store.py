"""
Holdout experiments (WS11): does the agent cause more conversions?

A running experiment keeps a fixed share of visitors (the holdout) away from
the agent: the widget doesn't appear for them. Everyone else gets the agent.
Both arms are measured the same way, on the site's own goal, so the
difference between them is the agent's effect.

* Assignment is deterministic, from the run id and the widget's anonymous
  visitor id, and stored on first sight, so a visitor stays in one arm.
* The goal is reached on the site itself: a goal page (``goal_path``, matched
  by the widget in both arms) or a ``FluidBuddha.conversion()`` call. Leads the
  agent captures are not counted: the holdout can't produce them, so counting
  them would build the answer into the measurement.
* Changing the holdout share starts a new run; results are per run.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experiments.stats import lift

DEFAULT_HOLDOUT_PCT = 10
VISITOR_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
GOAL_NAME_RE = re.compile(r"^[\w.:-]{1,64}$")
# More events than this from one visitor are ignored (a looping page, a bot).
_MAX_EVENTS_PER_VISITOR = 50


@dataclass
class Experiment:
    id: uuid.UUID
    site_key: str
    holdout_pct: int
    goal_path: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]

    @property
    def running(self) -> bool:
        return self.status == "running"

    def public(self) -> dict:
        return {
            "id": str(self.id),
            "enabled": self.running,
            "holdout_pct": self.holdout_pct,
            "goal_path": self.goal_path,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


_COLS = "id, site_key, holdout_pct, goal_path, status, started_at, ended_at"


def _row(r) -> Experiment:
    return Experiment(**{k: r[k] for k in
                         ("id", "site_key", "holdout_pct", "goal_path", "status",
                          "started_at", "ended_at")})


def assign_arm(experiment_id: uuid.UUID, visitor_id: str, holdout_pct: int) -> str:
    """Deterministic: the same visitor in the same run always lands in the same arm."""
    h = hashlib.sha256(f"{experiment_id}:{visitor_id}".encode()).digest()
    bucket = int.from_bytes(h[:8], "big") % 10_000
    return "holdout" if bucket < holdout_pct * 100 else "agent"


def clean_goal_path(raw: Optional[str]) -> Optional[str]:
    path = (raw or "").strip()
    if not path:
        return None
    if not path.startswith("/") or len(path) > 300 or any(c in path for c in "?#\n\r"):
        raise ValueError("The goal page must be a path on your site, like /thank-you")
    return path.rstrip("/") or "/"


async def current(db: AsyncSession, site_key: str) -> Optional[Experiment]:
    """The site's latest run (running or stopped), or None."""
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM experiments WHERE site_key = :k "
             "ORDER BY started_at DESC LIMIT 1"),
        {"k": site_key},
    )).mappings().first()
    return _row(row) if row else None


async def get(db: AsyncSession, site_key: str, experiment_id: uuid.UUID) -> Optional[Experiment]:
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM experiments WHERE id = :id AND site_key = :k"),
        {"id": experiment_id, "k": site_key},
    )).mappings().first()
    return _row(row) if row else None


async def configure(
    db: AsyncSession, site_key: str, *, enabled: bool, holdout_pct: int,
    goal_path: Optional[str],
) -> tuple[Optional[Experiment], bool]:
    """Apply the console settings. Returns ``(experiment, started_new_run)``."""
    exp = await current(db, site_key)
    started = False
    if enabled:
        if exp is None or not exp.running or exp.holdout_pct != holdout_pct:
            if exp is not None and exp.running:
                await _stop(db, exp.id)
            new_id = uuid.uuid4()
            await db.execute(
                text("INSERT INTO experiments (id, site_key, holdout_pct, goal_path) "
                     "VALUES (:id, :k, :pct, :goal)"),
                {"id": new_id, "k": site_key, "pct": holdout_pct, "goal": goal_path},
            )
            started = True
        else:
            await db.execute(text("UPDATE experiments SET goal_path = :goal WHERE id = :id"),
                             {"goal": goal_path, "id": exp.id})
    elif exp is not None and exp.running:
        await _stop(db, exp.id)
    await db.commit()
    return await current(db, site_key), started


async def restart(db: AsyncSession, site_key: str) -> Optional[Experiment]:
    exp = await current(db, site_key)
    if exp is None:
        return None
    exp, _ = await configure(db, site_key, enabled=False, holdout_pct=exp.holdout_pct,
                             goal_path=exp.goal_path)
    assert exp is not None
    exp, _ = await configure(db, site_key, enabled=True, holdout_pct=exp.holdout_pct,
                             goal_path=exp.goal_path)
    return exp


async def _stop(db: AsyncSession, experiment_id: uuid.UUID) -> None:
    await db.execute(
        text("UPDATE experiments SET status = 'stopped', ended_at = now() WHERE id = :id"),
        {"id": experiment_id},
    )


# ---- the widget's side ---------------------------------------------------------

async def enroll(db: AsyncSession, site_key: str, visitor_id: str) -> Optional[dict]:
    """Put a visitor in an arm of the running experiment (idempotent)."""
    exp = await current(db, site_key)
    if exp is None or not exp.running:
        return None
    arm = assign_arm(exp.id, visitor_id, exp.holdout_pct)
    await db.execute(
        text("INSERT INTO experiment_visitors (experiment_id, visitor_id, arm) "
             "VALUES (:e, :v, :arm) ON CONFLICT DO NOTHING"),
        {"e": exp.id, "v": visitor_id, "arm": arm},
    )
    await db.commit()
    return {"experiment_id": str(exp.id), "arm": arm, "goal_path": exp.goal_path}


async def record_conversion(
    db: AsyncSession, site_key: str, experiment_id: uuid.UUID, visitor_id: str,
    name: str, value: Optional[float],
) -> bool:
    """Count a goal for an enrolled visitor of the site's running experiment."""
    exp = await current(db, site_key)
    if exp is None or not exp.running or exp.id != experiment_id:
        return False
    res = await db.execute(
        text("UPDATE experiment_visitors SET conversions = conversions + 1, "
             "first_conversion_at = COALESCE(first_conversion_at, now()) "
             "WHERE experiment_id = :e AND visitor_id = :v AND conversions < :cap"),
        {"e": exp.id, "v": visitor_id, "cap": _MAX_EVENTS_PER_VISITOR},
    )
    if not (res.rowcount or 0):
        await db.rollback()
        return False  # never enrolled (or over the cap)
    await db.execute(
        text("INSERT INTO experiment_events (experiment_id, visitor_id, name, value) "
             "VALUES (:e, :v, :n, :val)"),
        {"e": exp.id, "v": visitor_id, "n": name, "val": value},
    )
    await db.commit()
    return True


# ---- results --------------------------------------------------------------------

async def results(db: AsyncSession, exp: Experiment) -> dict:
    counts = {
        r["arm"]: r for r in (await db.execute(
            text("SELECT arm, count(*) AS visitors, "
                 "count(first_conversion_at) AS converters "
                 "FROM experiment_visitors WHERE experiment_id = :e GROUP BY arm"),
            {"e": exp.id},
        )).mappings().all()
    }

    def n(arm: str, col: str) -> int:
        return int(counts[arm][col]) if arm in counts else 0

    summary = lift(n("agent", "converters"), n("agent", "visitors"),
                   n("holdout", "converters"), n("holdout", "visitors"))

    # Cumulative rates by day, so the dashboard can show the gap settling.
    days = (await db.execute(
        text("SELECT date_trunc('day', first_seen) AS day, arm, count(*) AS visitors, "
             "count(first_conversion_at) AS converters FROM experiment_visitors "
             "WHERE experiment_id = :e GROUP BY 1, 2 ORDER BY 1"),
        {"e": exp.id},
    )).mappings().all()
    series: list[dict] = []
    totals = {"agent": [0, 0], "holdout": [0, 0]}
    for day in sorted({r["day"] for r in days}):
        for r in (r for r in days if r["day"] == day):
            totals[r["arm"]][0] += int(r["visitors"])
            totals[r["arm"]][1] += int(r["converters"])
        series.append({
            "day": day.date().isoformat(),
            **{f"{arm}_rate": (c / v if v else None) for arm, (v, c) in totals.items()},
            **{f"{arm}_visitors": v for arm, (v, _) in totals.items()},
        })

    goals = [dict(r) for r in (await db.execute(
        text("SELECT e.name, v.arm, count(*) AS events FROM experiment_events e "
             "JOIN experiment_visitors v ON v.experiment_id = e.experiment_id "
             "AND v.visitor_id = e.visitor_id WHERE e.experiment_id = :e "
             "GROUP BY 1, 2 ORDER BY 3 DESC"),
        {"e": exp.id},
    )).mappings().all()]

    return {"experiment": exp.public(), "lift": summary.to_dict(),
            "series": series, "goals": goals}
