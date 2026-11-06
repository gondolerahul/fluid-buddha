"""
Proactive triggers (M2-3): the agent speaks up first, at the right moment.

A rule says *when* (time on page, scroll depth, leaving the page, coming back),
*where* (page globs, or everywhere), *what* (a short message) and *how* (a
nudge bubble by the launcher, or opening the panel). The widget evaluates the
rules in the visitor's browser — cheaply, nothing runs until a rule could fire
— and caps them (once per page view, ``max_per_day`` per visitor, silence for
the visit after a dismiss). It reports what happened (shown, clicked,
dismissed, engaged = went on to ask something) so each rule's performance shows
in the console.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

KINDS = ("time_on_page", "scroll_depth", "exit_intent", "return_visit")
EVENTS = ("shown", "clicked", "dismissed", "engaged")
MAX_RULES = 20
# Per visitor, rule, event and day; more is a loop or a bot.
_MAX_EVENTS_PER_DAY = 5


class RuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    kind: Literal["time_on_page", "scroll_depth", "exit_intent", "return_visit"]
    seconds: Optional[int] = Field(None, ge=3, le=600)          # time_on_page
    percent: Optional[int] = Field(None, ge=10, le=100)         # scroll_depth
    visits: Optional[int] = Field(None, ge=2, le=50)            # return_visit
    within_days: Optional[int] = Field(None, ge=1, le=90)       # return_visit
    pages: list[str] = Field(default_factory=list, max_length=20)
    message: str = Field(..., min_length=1, max_length=280)
    # Let the agent write the opener for the page the visitor is on; ``message``
    # is the fallback (M2-3 follow-up).
    compose: bool = False
    action: Literal["nudge", "open"] = "nudge"
    max_per_day: int = Field(1, ge=1, le=10)
    priority: int = Field(50, ge=0, le=100)

    @field_validator("pages")
    @classmethod
    def _pages(cls, v: list[str]) -> list[str]:
        out = []
        for p in v:
            p = p.strip()
            if not p:
                continue
            if not p.startswith("/") or len(p) > 200 or any(c in p for c in "?#\n "):
                raise ValueError("pages are paths on your site, like /pricing or /blog/*")
            out.append(p)
        return out

    @model_validator(mode="after")
    def _params(self) -> "RuleIn":
        if self.kind == "time_on_page" and self.seconds is None:
            self.seconds = 20
        if self.kind == "scroll_depth" and self.percent is None:
            self.percent = 60
        if self.kind == "return_visit":
            self.visits = self.visits or 2
            self.within_days = self.within_days or 30
        return self

    def params(self) -> dict[str, int]:
        keys = {"time_on_page": ("seconds",), "scroll_depth": ("percent",),
                "exit_intent": (), "return_visit": ("visits", "within_days")}[self.kind]
        return {k: getattr(self, k) for k in keys}


_COLS = ("id, name, enabled, kind, params, pages, message, compose, action, max_per_day, priority, "
         "created_at, updated_at")


def _row(r: Any) -> dict:
    params = r["params"] if isinstance(r["params"], dict) else json.loads(r["params"] or "{}")
    return {"id": str(r["id"]), "name": r["name"], "enabled": r["enabled"], "kind": r["kind"],
            **params, "pages": list(r["pages"] or []), "message": r["message"],
            "compose": bool(r["compose"]), "action": r["action"], "max_per_day": r["max_per_day"], "priority": r["priority"],
            "updated_at": r["updated_at"].isoformat()}


async def rules(db: AsyncSession, site_key: str, *, enabled_only: bool = False) -> list[dict]:
    rows = (await db.execute(text(
        f"SELECT {_COLS} FROM trigger_rules WHERE site_key = :s "
        + ("AND enabled " if enabled_only else "")
        + "ORDER BY priority DESC, created_at"), {"s": site_key})).mappings().all()
    return [_row(r) for r in rows]


async def create(db: AsyncSession, site_key: str, rule: RuleIn) -> dict:
    n = (await db.execute(text("SELECT count(*) FROM trigger_rules WHERE site_key = :s"),
                          {"s": site_key})).scalar()
    if n >= MAX_RULES:
        raise ValueError(f"A site can have up to {MAX_RULES} triggers.")
    r = (await db.execute(text(
        "INSERT INTO trigger_rules (id, site_key, name, enabled, kind, params, pages, message, "
        "compose, action, max_per_day, priority) VALUES (:id, :s, :n, :e, :k, CAST(:p AS jsonb), :pg, "
        f":m, :c, :a, :mx, :pr) RETURNING {_COLS}"),
        {"id": uuid.uuid4(), "s": site_key, "n": rule.name, "e": rule.enabled, "k": rule.kind,
         "p": json.dumps(rule.params()), "pg": rule.pages, "m": rule.message, "c": rule.compose,
         "a": rule.action, "mx": rule.max_per_day, "pr": rule.priority})).mappings().one()
    return _row(r)


async def update(db: AsyncSession, site_key: str, rule_id: uuid.UUID, rule: RuleIn) -> Optional[dict]:
    r = (await db.execute(text(
        "UPDATE trigger_rules SET name = :n, enabled = :e, kind = :k, params = CAST(:p AS jsonb), "
        "pages = :pg, message = :m, compose = :c, action = :a, max_per_day = :mx, priority = :pr, "
        f"updated_at = now() WHERE id = :id AND site_key = :s RETURNING {_COLS}"),
        {"id": rule_id, "s": site_key, "n": rule.name, "e": rule.enabled, "k": rule.kind,
         "p": json.dumps(rule.params()), "pg": rule.pages, "m": rule.message, "c": rule.compose,
         "a": rule.action, "mx": rule.max_per_day, "pr": rule.priority})).mappings().first()
    if r:
        # What the agent wrote for the old version of the rule is stale.
        await db.execute(text("DELETE FROM trigger_messages WHERE rule_id = :id"), {"id": rule_id})
    return _row(r) if r else None


async def delete(db: AsyncSession, site_key: str, rule_id: uuid.UUID) -> bool:
    return bool((await db.execute(text(
        "DELETE FROM trigger_rules WHERE id = :id AND site_key = :s"),
        {"id": rule_id, "s": site_key})).rowcount)


def public(rule: dict) -> dict:
    """What the widget needs (no names or timestamps)."""
    return {k: rule[k] for k in ("id", "kind", "pages", "message", "compose", "action", "max_per_day",
                                 "priority", "seconds", "percent", "visits", "within_days")
            if k in rule}


async def record(db: AsyncSession, site_key: str, rule_id: uuid.UUID, visitor_id: str,
                 event: str, page: Optional[str]) -> bool:
    res = await db.execute(text(
        "INSERT INTO trigger_events (site_key, rule_id, visitor_id, event, page) "
        "SELECT :s, :r, :v, :e, :pg WHERE EXISTS (SELECT 1 FROM trigger_rules WHERE id = :r "
        "AND site_key = :s) AND (SELECT count(*) FROM trigger_events WHERE rule_id = :r "
        "AND visitor_id = :v AND event = :e AND at > now() - interval '1 day') < :cap"),
        {"s": site_key, "r": rule_id, "v": visitor_id, "e": event, "pg": (page or "")[:300] or None,
         "cap": _MAX_EVENTS_PER_DAY})
    return bool(res.rowcount)


async def stats(db: AsyncSession, site_key: str, days: int = 30) -> dict[str, dict]:
    """Per rule: distinct visitors shown / clicked / dismissed / engaged, and rates."""
    rows = (await db.execute(text(
        "SELECT rule_id, event, count(DISTINCT visitor_id) AS n FROM trigger_events "
        "WHERE site_key = :s AND at > now() - make_interval(days => :d) GROUP BY 1, 2"),
        {"s": site_key, "d": days})).mappings().all()
    out: dict[str, dict] = {}
    for r in rows:
        out.setdefault(str(r["rule_id"]), {e: 0 for e in EVENTS})[r["event"]] = int(r["n"])
    for s in out.values():
        s["click_rate"] = s["clicked"] / s["shown"] if s["shown"] else None
        s["engage_rate"] = s["engaged"] / s["shown"] if s["shown"] else None
    return out
