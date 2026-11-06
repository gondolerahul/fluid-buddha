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
* Bots aren't enrolled (``bots.py``); a run only counts how many were refused.
* The verdict uses an always-valid interval, so the dashboard can be read
  daily without inflating false wins (``stats.py``); ``plan`` says how many
  visitors a given lift needs and how long that takes at the current traffic.

Variant tests (M2-4) use the same machinery for 2-4 variants of one setting
(``SUBJECTS``): the visitor's arm is a variant key (``a`` is the control) or
``holdout``; the widget applies the variant's ``overrides``; the results
compare each variant with the control; ``promote`` makes a variant the site's
default and ends the run. A site runs one experiment at a time, of either kind.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experiments.stats import lift, sample_size, sample_size_arms, variant_verdict

DEFAULT_HOLDOUT_PCT = 10
VISITOR_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
GOAL_NAME_RE = re.compile(r"^[\w.:-]{1,64}$")
# More events than this from one visitor are ignored (a looping page, a bot).
_MAX_EVENTS_PER_VISITOR = 50


SUBJECTS = ("greeting", "trigger", "tour", "persona", "design", "regions")
VARIANT_KEYS = ("a", "b", "c", "d")
DESIGNS = ("level1", "level2", "level3")


class Conflict(Exception):
    """Another kind of experiment is running on the site."""


@dataclass
class Experiment:
    id: uuid.UUID
    site_key: str
    holdout_pct: int
    goal_path: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime]
    bots_ignored: int = 0
    name: Optional[str] = None
    subject: Optional[str] = None       # None: the agent vs a holdout (WS11)
    variants: Any = None                # [{key, label, overrides}], control first
    winner: Optional[str] = None
    promoted_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if isinstance(self.variants, str):
            self.variants = json.loads(self.variants)
        self.variants = list(self.variants or [])

    @property
    def running(self) -> bool:
        return self.status == "running"

    @property
    def is_test(self) -> bool:
        return self.subject is not None

    def variant(self, key: Optional[str]) -> Optional[dict]:
        return next((v for v in self.variants if v["key"] == key), None)

    def public(self) -> dict:
        out = {
            "id": str(self.id),
            "enabled": self.running,
            "holdout_pct": self.holdout_pct,
            "goal_path": self.goal_path,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "bots_ignored": self.bots_ignored,
        }
        if self.is_test:
            out.update(name=self.name, subject=self.subject, variants=self.variants,
                       winner=self.winner,
                       promoted_at=self.promoted_at.isoformat() if self.promoted_at else None)
        return out


_FIELDS = ("id", "site_key", "holdout_pct", "goal_path", "status", "started_at",
           "ended_at", "bots_ignored", "name", "subject", "variants", "winner", "promoted_at")
_COLS = ", ".join(_FIELDS)
# Planner defaults: a 3 % goal rate until the holdout shows its own, and a
# +20 % relative lift to look for.
DEFAULT_BASELINE = 0.03
DEFAULT_MDE = 0.20


def _row(r) -> Experiment:
    return Experiment(**{k: r[k] for k in _FIELDS})


def assign_arm(experiment_id: uuid.UUID, visitor_id: str, holdout_pct: int,
               variants: Optional[list[str]] = None) -> str:
    """Deterministic: the same visitor in the same run always lands in the same
    arm. The holdout takes the first ``holdout_pct`` %; the rest is the agent,
    or split equally between the ``variants``."""
    h = hashlib.sha256(f"{experiment_id}:{visitor_id}".encode()).digest()
    bucket = int.from_bytes(h[:8], "big") % 10_000
    cut = holdout_pct * 100
    if bucket < cut:
        return "holdout"
    if not variants:
        return "agent"
    return variants[(bucket - cut) * len(variants) // (10_000 - cut)]


def clean_goal_path(raw: Optional[str]) -> Optional[str]:
    path = (raw or "").strip()
    if not path:
        return None
    if not path.startswith("/") or len(path) > 300 or any(c in path for c in "?#\n\r"):
        raise ValueError("The goal page must be a path on your site, like /thank-you")
    return path.rstrip("/") or "/"


async def current(db: AsyncSession, site_key: str, *,
                  kind: Optional[str] = None) -> Optional[Experiment]:
    """The site's latest run (running or stopped), or None. ``kind``:
    ``holdout`` or ``test`` to look at one kind only."""
    where = {"holdout": "AND subject IS NULL ", "test": "AND subject IS NOT NULL "}.get(kind or "", "")
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM experiments WHERE site_key = :k {where}"
             "ORDER BY started_at DESC LIMIT 1"),
        {"k": site_key},
    )).mappings().first()
    return _row(row) if row else None


async def running_test(db: AsyncSession, site_key: str) -> Optional[Experiment]:
    exp = await current(db, site_key)
    return exp if exp is not None and exp.running and exp.is_test else None


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
    """Apply the console settings of the holdout run. Returns
    ``(experiment, started_new_run)``. Raises ``Conflict`` while a variant
    test runs (one experiment at a time)."""
    exp = await current(db, site_key, kind="holdout")
    started = False
    if enabled and await running_test(db, site_key):
        raise Conflict("A variant test is running on this site. Stop it first.")
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
    return await current(db, site_key, kind="holdout"), started


async def restart(db: AsyncSession, site_key: str) -> Optional[Experiment]:
    exp = await current(db, site_key, kind="holdout")
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

async def enroll(db: AsyncSession, site_key: str, visitor_id: str,
                 bot: bool = False) -> Optional[dict]:
    """Put a visitor in an arm of the running experiment (idempotent). A bot
    is counted as turned away and not enrolled."""
    exp = await current(db, site_key)
    if exp is None or not exp.running:
        return None
    if bot:
        await db.execute(
            text("UPDATE experiments SET bots_ignored = bots_ignored + 1 WHERE id = :id"),
            {"id": exp.id})
        await db.commit()
        return None
    arm = assign_arm(exp.id, visitor_id, exp.holdout_pct,
                     [v["key"] for v in exp.variants] or None)
    await db.execute(
        text("INSERT INTO experiment_visitors (experiment_id, visitor_id, arm) "
             "VALUES (:e, :v, :arm) ON CONFLICT DO NOTHING"),
        {"e": exp.id, "v": visitor_id, "arm": arm},
    )
    await db.commit()
    v = exp.variant(arm)
    return {"experiment_id": str(exp.id), "arm": arm, "goal_path": exp.goal_path,
            "overrides": (v or {}).get("overrides") or {}}


async def overrides_for(db: AsyncSession, site_key: str, experiment_id: Any, arm: Any) -> dict:
    """A variant's overrides, for the ones applied on the server (greeting,
    persona, tour). Only a running test's own variants; anything else is {}."""
    try:
        eid = uuid.UUID(str(experiment_id))
    except ValueError:
        return {}
    exp = await running_test(db, site_key)
    if exp is None or exp.id != eid:
        return {}
    v = exp.variant(str(arm or ""))
    return dict((v or {}).get("overrides") or {})


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
    counts = await _counts(db, exp)
    (av, ac), (hv, hc) = counts.get("agent", (0, 0)), counts.get("holdout", (0, 0))
    summary = lift(ac, av, hc, hv)

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


async def _counts(db: AsyncSession, exp: Experiment) -> dict[str, tuple[int, int]]:
    """``{arm: (visitors, converters)}`` for a run."""
    rows = (await db.execute(
        text("SELECT arm, count(*) AS visitors, count(first_conversion_at) AS converters "
             "FROM experiment_visitors WHERE experiment_id = :e GROUP BY arm"),
        {"e": exp.id},
    )).mappings().all()
    return {r["arm"]: (int(r["visitors"]), int(r["converters"])) for r in rows}


async def plan(db: AsyncSession, exp: Optional[Experiment], *,
               baseline: Optional[float] = None, mde: float = DEFAULT_MDE,
               holdout_pct: Optional[int] = None) -> dict:
    """How many visitors the run needs to show a ``mde`` relative lift over
    ``baseline`` (default: the holdout's own rate once it has 30 visitors and
    a conversion, else 3 %), and how long that takes at the run's traffic."""
    counts = await _counts(db, exp) if exp else {}
    hv, hc = counts.get("holdout", (0, 0))
    av, _ = counts.get("agent", (0, 0))
    observed = hc / hv if hv >= 30 and hc > 0 else None
    if baseline is not None:
        base, source = baseline, "given"
    elif observed is not None:
        base, source = observed, "observed"
    else:
        base, source = DEFAULT_BASELINE, "default"
    pct = holdout_pct or (exp.holdout_pct if exp else DEFAULT_HOLDOUT_PCT)
    need = sample_size(base, mde, pct / 100)
    so_far = hv + av
    per_day = days_left = None
    if exp is not None and so_far:
        end = exp.ended_at or datetime.now(exp.started_at.tzinfo)
        days = max((end - exp.started_at).total_seconds() / 86_400, 1.0)
        per_day = so_far / days
        if need:
            days_left = max(0.0, (need["total"] - so_far) / per_day)
    return {
        "baseline": base, "baseline_source": source, "observed_baseline": observed,
        "mde": mde, "holdout_pct": pct, "needed": need,
        "visitors_so_far": so_far, "visitors_per_day": per_day, "days_left": days_left,
        "reached": bool(need) and so_far >= need["total"],
    }


# ---- variant tests (M2-4) -------------------------------------------------------

def clean_overrides(subject: str, raw: Any, *, personas: list[str],
                    rule_ids: list[str]) -> dict:
    """One variant's settings for ``subject``, checked against the site."""
    o = raw if isinstance(raw, dict) else {}
    if subject == "greeting":
        g = str(o.get("greeting") or "").strip()
        if not 1 <= len(g) <= 300:
            raise ValueError("Each greeting needs 1-300 characters.")
        return {"greeting": g}
    if subject == "trigger":
        ids = o.get("triggers")
        if not isinstance(ids, list) or any(str(i) not in rule_ids for i in ids):
            raise ValueError("Pick triggers from this site's list (or none).")
        return {"triggers": sorted({str(i) for i in ids})}
    if subject == "tour":
        if not isinstance(o.get("tour"), bool):
            raise ValueError("Each variant turns the tour on or off.")
        return {"tour": o["tour"]}
    if subject == "persona":
        p = str(o.get("persona") or "")
        if p and p not in personas:
            raise ValueError(f"Unknown persona: {p}")
        return {"persona": p}
    if subject == "design":
        d = str(o.get("design") or "")
        if d not in DESIGNS:
            raise ValueError("The design level is level1, level2 or level3.")
        return {"design": d}
    if subject == "regions":
        # Generated regions (Phase 1) against the page's own content.
        if not isinstance(o.get("regions"), bool):
            raise ValueError("Each variant turns generated regions on or off.")
        return {"regions": o["regions"]}
    raise ValueError(f"Can't test {subject!r}")


def clean_variants(subject: str, variants: list[dict], **site: Any) -> list[dict]:
    if subject not in SUBJECTS:
        raise ValueError(f"Can't test {subject!r}")
    if not 2 <= len(variants) <= len(VARIANT_KEYS):
        raise ValueError(f"A test has 2 to {len(VARIANT_KEYS)} variants.")
    out = []
    for key, v in zip(VARIANT_KEYS, variants):
        label = str(v.get("label") or "").strip()[:60] or ("Control" if key == "a" else f"Variant {key.upper()}")
        out.append({"key": key, "label": label,
                    "overrides": clean_overrides(subject, v.get("overrides"), **site)})
    if len({json.dumps(v["overrides"], sort_keys=True) for v in out}) != len(out):
        raise ValueError("Two variants are the same: make each one different.")
    return out


async def start_test(db: AsyncSession, site_key: str, *, name: str, subject: str,
                     variants: list[dict], holdout_pct: int,
                     goal_path: Optional[str]) -> Experiment:
    """Start a variant test (variants already cleaned). A running experiment
    of either kind is stopped first: one at a time."""
    exp = await current(db, site_key)
    if exp is not None and exp.running:
        await _stop(db, exp.id)
    new_id = uuid.uuid4()
    await db.execute(
        text("INSERT INTO experiments (id, site_key, holdout_pct, goal_path, name, subject, variants) "
             "VALUES (:id, :k, :pct, :goal, :name, :subject, CAST(:variants AS jsonb))"),
        {"id": new_id, "k": site_key, "pct": holdout_pct, "goal": goal_path, "name": name,
         "subject": subject, "variants": json.dumps(variants)},
    )
    await db.commit()
    exp = await get(db, site_key, new_id)
    assert exp is not None
    return exp


async def stop_test(db: AsyncSession, exp: Experiment) -> Experiment:
    if exp.running:
        await _stop(db, exp.id)
        await db.commit()
    return await get(db, exp.site_key, exp.id) or exp


async def list_tests(db: AsyncSession, site_key: str, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        text(f"SELECT {_COLS} FROM experiments WHERE site_key = :k AND subject IS NOT NULL "
             "ORDER BY started_at DESC LIMIT :n"),
        {"k": site_key, "n": limit},
    )).mappings().all()
    tests = [_row(r) for r in rows]
    counts = {}
    if tests:
        for r in (await db.execute(
            text("SELECT experiment_id, count(*) AS n FROM experiment_visitors "
                 "WHERE experiment_id = ANY(:ids) GROUP BY 1"),
            {"ids": [t.id for t in tests]},
        )).mappings().all():
            counts[r["experiment_id"]] = int(r["n"])
    return [{**t.public(), "visitors": counts.get(t.id, 0)} for t in tests]


async def variant_results(db: AsyncSession, exp: Experiment, *, mde: float = DEFAULT_MDE) -> dict:
    """Each variant's rate, its comparison with the control at the split
    error budget, the run's verdict, and (with a holdout) the agent overall
    against the holdout."""
    counts = await _counts(db, exp)
    arms = [(v["key"], *counts.get(v["key"], (0, 0))) for v in exp.variants]
    planned = await variant_plan(db, exp, mde=mde)
    verdict = variant_verdict(arms, plan_reached=planned["reached"])
    variants = []
    for v in exp.variants:
        n, x = counts.get(v["key"], (0, 0))
        variants.append({**v, "visitors": n, "converters": x, "rate": x / n if n else None,
                         "vs_control": verdict["comparisons"].get(v["key"])})
    out: dict = {"experiment": exp.public(), "variants": variants,
                 "verdict": {k: verdict[k] for k in ("status", "winner", "alpha")},
                 "plan": planned, "holdout": None}
    if exp.holdout_pct:
        hn, hx = counts.get("holdout", (0, 0))
        an = sum(n for _, n, _ in arms)
        ax = sum(x for _, _, x in arms)
        out["holdout"] = lift(ax, an, hx, hn).to_dict()
    return out


async def variant_plan(db: AsyncSession, exp: Experiment, *, baseline: Optional[float] = None,
                    mde: float = DEFAULT_MDE) -> dict:
    """Visitors the test needs to find a ``mde`` relative lift over the
    control (its own rate once it has 30 visitors and a conversion), and how
    long that takes at the run's traffic."""
    counts = await _counts(db, exp)
    cn, cx = counts.get("a", (0, 0))
    observed = cx / cn if cn >= 30 and cx > 0 else None
    if baseline is not None:
        base, source = baseline, "given"
    elif observed is not None:
        base, source = observed, "observed"
    else:
        base, source = DEFAULT_BASELINE, "default"
    need = sample_size_arms(base, mde, len(exp.variants), exp.holdout_pct / 100)
    so_far = sum(n for n, _ in counts.values())
    per_day = days_left = None
    if so_far:
        end = exp.ended_at or datetime.now(exp.started_at.tzinfo)
        per_day = so_far / max((end - exp.started_at).total_seconds() / 86_400, 1.0)
        if need:
            days_left = max(0.0, (need["total"] - so_far) / per_day)
    return {"baseline": base, "baseline_source": source, "mde": mde, "needed": need,
            "visitors_so_far": so_far, "visitors_per_day": per_day, "days_left": days_left,
            "reached": bool(need) and so_far >= need["total"]}


async def mark_promoted(db: AsyncSession, exp: Experiment, key: str) -> Experiment:
    """Record the promoted variant and end the run (the caller has applied
    its settings as the site's defaults)."""
    await db.execute(
        text("UPDATE experiments SET winner = :w, promoted_at = now(), status = 'stopped', "
             "ended_at = COALESCE(ended_at, now()) WHERE id = :id"),
        {"w": key, "id": exp.id},
    )
    await db.commit()
    return await get(db, exp.site_key, exp.id) or exp
