"""
What the status page shows (M3-6): components measured every minute from the
readiness checks, and the incidents operators post.

Components, from the checks:

* ``api``    — the API, the widget and the console's backend: database,
               schema and Redis (down if any fails);
* ``voice``  — answers and the voice agent: the API, plus the AI provider
               (degraded when the model is failing);
* ``jobs``   — background work (emails, digests, retention): the jobs loop;
* ``email``  — sending email: the outbox isn't backing up.

A component's current state is its last sample, made worse by any open
incident that names it (major → degraded, critical → down). Uptime counts
every minute that wasn't ``down``.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

COMPONENTS = {
    "api": "API, widget and console",
    "voice": "Answers and voice agent",
    "jobs": "Background jobs",
    "email": "Email",
}
STATES = ("up", "degraded", "down")
IMPACTS = ("minor", "major", "critical", "maintenance")
STATUSES = ("investigating", "identified", "monitoring", "resolved", "scheduled")
KEEP_DAYS = 100
HISTORY_DAYS = 90


def components_from(checks: dict[str, dict]) -> dict[str, tuple[str, Optional[str]]]:
    """Readiness checks → component states."""
    def fails(*names: str) -> list[str]:
        return [n for n in names if not checks.get(n, {}).get("ok", True)]

    def why(names: list[str]) -> Optional[str]:
        return "; ".join(f"{n}: {checks[n].get('detail') or 'failing'}" for n in names) or None

    api_bad = fails("db", "migrations", "redis")
    out: dict[str, tuple[str, Optional[str]]] = {"api": ("down", why(api_bad)) if api_bad else ("up", None)}
    model_bad = fails("models")
    out["voice"] = ("down", why(api_bad)) if api_bad else (("degraded", why(model_bad)) if model_bad else ("up", None))
    jobs_bad = fails("scheduler")
    out["jobs"] = ("degraded", why(jobs_bad)) if jobs_bad else ("up", None)
    email_bad = fails("email")
    out["email"] = ("degraded", why(email_bad)) if email_bad else ("up", None)
    return out


async def record(db: AsyncSession, states: dict[str, tuple[str, Optional[str]]]) -> None:
    for comp, (state, detail) in states.items():
        await db.execute(text("INSERT INTO status_samples (component, state, detail) VALUES (:c, :s, :d)"),
                         {"c": comp, "s": state, "d": (detail or None) and detail[:300]})
    await db.execute(text("DELETE FROM status_samples WHERE at < now() - make_interval(days => :d)"),
                     {"d": KEEP_DAYS})


async def probe(db: AsyncSession, app: Any = None) -> dict[str, tuple[str, Optional[str]]]:
    """One measurement: the checks, then a sample per component."""
    from app.observability.health import check_all

    result = await check_all(app)
    states = components_from(result["checks"])
    await record(db, states)
    await db.commit()
    return states


# ---- incidents -----------------------------------------------------------------------

class StatusError(ValueError):
    pass


def _clean(raw: dict[str, Any], *, new: bool) -> dict[str, Any]:
    status = raw.get("status") or ("investigating" if new else "")
    if status not in STATUSES:
        raise StatusError(f"status is one of {', '.join(STATUSES)}")
    body = " ".join(str(raw.get("body") or "").split())[:2000]
    if not body:
        raise StatusError("say what's happening (body)")
    out: dict[str, Any] = {"status": status, "body": body}
    if new:
        title = " ".join(str(raw.get("title") or "").split())[:160]
        impact = raw.get("impact") or "minor"
        comps = [c for c in (raw.get("components") or []) if c in COMPONENTS]
        if not title:
            raise StatusError("give it a title")
        if impact not in IMPACTS:
            raise StatusError(f"impact is one of {', '.join(IMPACTS)}")
        out.update(title=title, impact=impact, components=comps)
    return out


async def open_incident(db: AsyncSession, raw: dict[str, Any]) -> dict[str, Any]:
    v = _clean(raw, new=True)
    iid = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO status_incidents (id, title, impact, status, components, resolved_at) "
        "VALUES (:id, :t, :i, :s, :c, CASE WHEN :s = 'resolved' THEN now() END)"),
        {"id": iid, "t": v["title"], "i": v["impact"], "s": v["status"], "c": v["components"]})
    await db.execute(text("INSERT INTO status_updates (incident_id, status, body) VALUES (:id, :s, :b)"),
                     {"id": iid, "s": v["status"], "b": v["body"]})
    await db.commit()
    return await get_incident(db, iid)  # type: ignore[return-value]


async def add_update(db: AsyncSession, incident_id: uuid.UUID, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    v = _clean(raw, new=False)
    hit = (await db.execute(text(
        "UPDATE status_incidents SET status = :s, resolved_at = CASE WHEN :s = 'resolved' THEN now() END "
        "WHERE id = :id RETURNING id"), {"s": v["status"], "id": incident_id})).first()
    if not hit:
        return None
    await db.execute(text("INSERT INTO status_updates (incident_id, status, body) VALUES (:id, :s, :b)"),
                     {"id": incident_id, "s": v["status"], "b": v["body"]})
    await db.commit()
    return await get_incident(db, incident_id)


async def get_incident(db: AsyncSession, incident_id: uuid.UUID) -> Optional[dict[str, Any]]:
    r = (await db.execute(text("SELECT * FROM status_incidents WHERE id = :id"), {"id": incident_id})).mappings().first()
    if not r:
        return None
    ups = (await db.execute(text(
        "SELECT status, body, at FROM status_updates WHERE incident_id = :id ORDER BY at DESC, id DESC"),
        {"id": incident_id})).mappings().all()
    return _incident(r, ups)


def _incident(r: Any, ups: Any) -> dict[str, Any]:
    return {"id": str(r["id"]), "title": r["title"], "impact": r["impact"], "status": r["status"],
            "components": list(r["components"] or []), "created_at": r["created_at"].isoformat(),
            "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            "updates": [{"status": u["status"], "body": u["body"], "at": u["at"].isoformat()} for u in ups]}


async def incidents(db: AsyncSession, *, days: int = 14) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT * FROM status_incidents WHERE resolved_at IS NULL OR resolved_at > now() - make_interval(days => :d) "
        "ORDER BY (resolved_at IS NULL) DESC, created_at DESC LIMIT 30"), {"d": days})).mappings().all()
    out = []
    for r in rows:
        ups = (await db.execute(text(
            "SELECT status, body, at FROM status_updates WHERE incident_id = :id ORDER BY at DESC, id DESC"),
            {"id": r["id"]})).mappings().all()
        out.append(_incident(r, ups))
    return out


# ---- the page's numbers --------------------------------------------------------------

_WORSE = {"up": 0, "degraded": 1, "down": 2}


async def summary(db: AsyncSession, days: int = HISTORY_DAYS) -> dict[str, Any]:
    """Each component now, its uptime and a bar per day; the incidents."""
    latest = {r["component"]: r for r in (await db.execute(text(
        "SELECT DISTINCT ON (component) component, state, detail, at FROM status_samples "
        "ORDER BY component, at DESC"))).mappings().all()}
    daily = (await db.execute(text(
        "SELECT component, (at AT TIME ZONE 'UTC')::date AS day, count(*) AS n, "
        "count(*) FILTER (WHERE state = 'down') AS down, count(*) FILTER (WHERE state = 'degraded') AS degraded "
        "FROM status_samples WHERE at > now() - make_interval(days => :d) GROUP BY 1, 2"), {"d": days})).mappings().all()
    incs = await incidents(db)
    # Open incidents count; maintenance only once it has started.
    open_incs = [i for i in incs if i["status"] not in ("resolved", "scheduled")]
    today = datetime.now(timezone.utc).date()
    comps = []
    for key, label in COMPONENTS.items():
        sample = latest.get(key)
        state = sample["state"] if sample else "up"
        for inc in open_incs:
            if key in inc["components"]:
                bump = {"critical": "down", "major": "degraded", "maintenance": "degraded"}.get(inc["impact"])
                if bump and _WORSE[bump] > _WORSE[state]:
                    state = bump
        rows = {r["day"]: r for r in daily if r["component"] == key}
        bars, n_total, n_down = [], 0, 0
        for i in range(days - 1, -1, -1):
            d: date = today - timedelta(days=i)
            r = rows.get(d)
            if r is None:
                bars.append({"day": d.isoformat(), "state": None, "uptime": None})
                continue
            n_total += r["n"]
            n_down += r["down"]
            st = "down" if r["down"] else ("degraded" if r["degraded"] else "up")
            bars.append({"day": d.isoformat(), "state": st, "uptime": round(1 - r["down"] / r["n"], 5)})
        comps.append({"key": key, "label": label, "state": state,
                      "detail": sample["detail"] if sample and sample["state"] != "up" else None,
                      "checked_at": sample["at"].isoformat() if sample else None,
                      "uptime": round(1 - n_down / n_total, 5) if n_total else None, "days": bars})
    worst = max((_WORSE[c["state"]] for c in comps), default=0)
    overall = {0: "operational", 1: "degraded", 2: "outage"}[worst]
    return {"overall": overall, "components": comps, "incidents": incs,
            "generated_at": datetime.now(timezone.utc).isoformat()}
