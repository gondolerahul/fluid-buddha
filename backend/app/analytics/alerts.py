"""
Per-site cost alerts (F-3): tell the site owner before the AI bill surprises
them, and before the daily spend cap switches their agent off.

Three kinds, each sent at most once per site per UTC day:

* ``threshold`` — today's AI cost passed the site's own alert amount
  (``site_integrations.cost_alert_usd``, set in the console);
* ``cap_80`` — today's cost reached 80 % of the daily spend cap
  (``PUBLIC_DAILY_SPEND_CAP_USD``), so the agent will soon pause;
* ``cap_100`` — the cap is reached: the agent is paused until midnight UTC.

The check runs where the spend cap is already checked, before each public
turn, so it costs nothing extra when neither a threshold nor a cap is set
(the site's threshold is cached for a minute). Sending happens in the
background: a turn never waits on Slack. Every alert is recorded (and shown
in the console), counted in ``fb_cost_alerts_total`` for operators, logged,
and posted to the site's Slack webhook when it has one.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

LEVELS = ("threshold", "cap_80", "cap_100")
_CACHE_S = 60.0
_threshold_cache: dict[str, tuple[float, Optional[float]]] = {}
_tasks: set[asyncio.Task] = set()   # keep background sends alive until done


def forget_threshold(site_key: str) -> None:
    """Drop the cached threshold (after the tenant changes it)."""
    _threshold_cache.pop(site_key, None)


async def site_threshold(db: AsyncSession, site_key: str) -> Optional[float]:
    hit = _threshold_cache.get(site_key)
    now = time.monotonic()
    if hit and now - hit[0] < _CACHE_S:
        return hit[1]
    value = (await db.execute(
        text("SELECT cost_alert_usd FROM site_integrations WHERE site_key = :s"),
        {"s": site_key},
    )).scalar()
    value = float(value) if value and value > 0 else None
    _threshold_cache[site_key] = (now, value)
    return value


def due(spent: float, cap: float, threshold: Optional[float]) -> list[tuple[str, float]]:
    """``[(level, limit)]`` that today's ``spent`` has reached."""
    out: list[tuple[str, float]] = []
    if threshold and spent >= threshold:
        out.append(("threshold", threshold))
    if cap > 0 and spent >= 0.8 * cap:
        out.append(("cap_80", cap))
    if cap > 0 and spent >= cap:
        out.append(("cap_100", cap))
    return out


def message(site_name: str, level: str, spent: float, limit: float) -> str:
    if level == "threshold":
        return (f":warning: *{site_name}*: today's AI cost is ${spent:,.2f}, past your "
                f"alert of ${limit:,.2f}.")
    if level == "cap_80":
        return (f":warning: *{site_name}*: today's AI cost is ${spent:,.2f}, 80% of the "
                f"${limit:,.2f} daily cap. The agent pauses for the day when it is reached.")
    return (f":octagonal_sign: *{site_name}*: the ${limit:,.2f} daily cost cap is reached "
            f"(${spent:,.2f}). The agent is paused until midnight UTC.")


def schedule(site_key: str, spent: float, cap: float, threshold: Optional[float]) -> None:
    """Send whatever alerts are due, in the background (never blocks a turn)."""
    levels = due(spent, cap, threshold)
    if not levels:
        return
    task = asyncio.get_running_loop().create_task(_send(site_key, spent, levels))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _send(site_key: str, spent: float, levels: list[tuple[str, float]]) -> None:
    from app.db import session_scope
    from app.leads.delivery import _post
    from app.observability.metrics import COST_ALERTS

    try:
        async with session_scope() as db:
            new = []
            for level, limit in levels:
                inserted = (await db.execute(text(
                    "INSERT INTO cost_alerts (site_key, day, level, spent_usd, limit_usd) "
                    "VALUES (:s, (now() AT TIME ZONE 'UTC')::date, :lv, :sp, :lim) "
                    "ON CONFLICT DO NOTHING RETURNING level"),
                    {"s": site_key, "lv": level, "sp": spent, "lim": limit})).scalar()
                if inserted:
                    new.append((level, limit))
            if not new:
                return
            row = (await db.execute(text(
                "SELECT w.name, i.slack_webhook_url FROM tenant_websites w "
                "LEFT JOIN site_integrations i ON i.site_key = w.site_key "
                "WHERE w.site_key = :s"), {"s": site_key})).mappings().first()
        name = (row and row["name"]) or site_key
        slack = row and row["slack_webhook_url"]
        for level, limit in new:
            COST_ALERTS.labels(level).inc()
            logger.warning("cost alert %s for site %s: spent $%.2f of $%.2f",
                           level, site_key, spent, limit)
            error = None
            if slack:
                try:
                    body = json.dumps({"text": message(name, level, spent, limit)}).encode()
                    await _post(slack, body, {"Content-Type": "application/json"}, _transport)
                except Exception as exc:   # recorded, never raised into a turn
                    error = str(exc)[:500]
            async with session_scope() as db:
                await db.execute(text(
                    "UPDATE cost_alerts SET delivered = :d, error = :e WHERE site_key = :s "
                    "AND day = (now() AT TIME ZONE 'UTC')::date AND level = :lv"),
                    {"d": bool(slack) and error is None, "e": error, "s": site_key, "lv": level})
    except Exception:
        logger.exception("cost alert for site %s failed", site_key)


# Tests swap in an httpx.MockTransport here.
_transport = None


async def recent(db: AsyncSession, site_key: str, days: int = 7) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT day, level, spent_usd, limit_usd, delivered, error, at FROM cost_alerts "
        "WHERE site_key = :s AND day > (now() AT TIME ZONE 'UTC')::date - CAST(:n AS integer) "
        "ORDER BY at DESC"), {"s": site_key, "n": days})).mappings().all()
    return [{**dict(r), "day": r["day"].isoformat(), "at": r["at"].isoformat()} for r in rows]


async def drain() -> None:
    """Wait for background sends (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
