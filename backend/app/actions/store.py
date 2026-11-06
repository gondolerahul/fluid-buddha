"""
Actions and their runs (M2-8).

An action is set up per site in the console. When the agent calls one, a run
is *proposed*: the inputs are checked and stored with a summary for the
visitor, and nothing else happens. Only the visitor's confirmation (from the
widget, for the same conversation, within ``CONFIRM_WINDOW``) runs it; the
run then records the outcome. Limits: proposals per conversation and runs per
action per hour.

Secrets (a Razorpay key secret and webhook secret, a webhook signing secret)
are encrypted at rest and never returned to the browser; the console sees
only whether one is set.
"""
from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.fields import (
    ActionConfigError, clean_config, clean_name, fields_for, price, summary, validate_inputs,
)
from app.security.secrets import decrypt, encrypt

CONFIRM_WINDOW_S = 15 * 60
PROPOSALS_PER_SESSION_HOUR = 10
_TTL_S = 30.0


@dataclass
class Action:
    id: uuid.UUID
    site_key: str
    kind: str
    name: str
    label: str
    description: str
    enabled: bool
    config: dict[str, Any]
    has_secret: bool = False
    fields: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tool_name(self) -> str:
        return f"action_{self.name}"

    def public(self) -> dict[str, Any]:
        return {"id": str(self.id), "kind": self.kind, "name": self.name, "label": self.label,
                "description": self.description, "enabled": self.enabled,
                "config": self.config, "has_secret": self.has_secret, "fields": self.fields}


def _action(r: Any) -> Action:
    cfg = r["config"] if isinstance(r["config"], dict) else json.loads(r["config"] or "{}")
    return Action(id=r["id"], site_key=r["site_key"], kind=r["kind"], name=r["name"],
                  label=r["label"], description=r["description"], enabled=r["enabled"],
                  config=cfg, has_secret=bool(r["secret_enc"]), fields=fields_for(r["kind"], cfg))


# ---- secrets ----------------------------------------------------------------

def new_signing_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


async def secrets_of(db: AsyncSession, action_id: uuid.UUID) -> dict[str, str]:
    raw = (await db.execute(text("SELECT secret_enc FROM site_actions WHERE id = :id"),
                            {"id": action_id})).scalar()
    return json.loads(decrypt(raw)) if raw else {}


def _clean_secrets(kind: str, given: Optional[dict[str, Any]], current: dict[str, str]) -> dict[str, str]:
    """Merge newly typed secrets over the stored ones (blank = keep)."""
    out = dict(current)
    for k, v in (given or {}).items():
        if k in ("key_secret", "webhook_secret") and isinstance(v, str) and v.strip():
            out[k] = v.strip()[:200]
    if kind == "payment_link" and not out.get("key_secret"):
        raise ActionConfigError("add the Razorpay key secret")
    if kind in ("trial", "webhook") and not out.get("signing_secret"):
        out["signing_secret"] = new_signing_secret()
    return {k: v for k, v in out.items() if k in ("key_secret", "webhook_secret", "signing_secret")}


# ---- console CRUD -------------------------------------------------------------

async def list_actions(db: AsyncSession, site_key: str) -> list[Action]:
    rows = (await db.execute(text(
        "SELECT * FROM site_actions WHERE site_key = :s ORDER BY created_at"),
        {"s": site_key})).mappings().all()
    return [_action(r) for r in rows]


async def get_action(db: AsyncSession, site_key: str, action_id: uuid.UUID) -> Optional[Action]:
    r = (await db.execute(text("SELECT * FROM site_actions WHERE id = :id AND site_key = :s"),
                          {"id": action_id, "s": site_key})).mappings().first()
    return _action(r) if r else None


async def save_action(db: AsyncSession, site_key: str, data: dict[str, Any],
                      action_id: Optional[uuid.UUID] = None) -> Action:
    """Create or update (the caller commits). Raises ActionConfigError."""
    current = await get_action(db, site_key, action_id) if action_id else None
    kind = current.kind if current else str(data.get("kind") or "")
    config = clean_config(kind, data.get("config"))
    name = clean_name(data.get("name") or (current.name if current else ""))
    label = " ".join(str(data.get("label") or "").split())[:80]
    if not label:
        raise ActionConfigError("add a label the visitor will see")
    desc = " ".join(str(data.get("description") or "").split())[:400]
    stored = await secrets_of(db, current.id) if current else {}
    sec = _clean_secrets(kind, data.get("secrets"), stored)
    params = {"s": site_key, "k": kind, "n": name, "l": label, "d": desc,
              "e": bool(data.get("enabled", True)), "c": json.dumps(config),
              "sec": encrypt(json.dumps(sec)) if sec else None}
    clash = (await db.execute(text(
        "SELECT 1 FROM site_actions WHERE site_key = :s AND name = :n AND id <> :id"),
        {"s": site_key, "n": name, "id": action_id or uuid.uuid4()})).first()
    if clash:
        raise ActionConfigError(f"another action is already called {name}")
    if current:
        r = (await db.execute(text(
            "UPDATE site_actions SET name = :n, label = :l, description = :d, enabled = :e, "
            "config = CAST(:c AS jsonb), secret_enc = :sec, updated_at = now() "
            "WHERE id = :id RETURNING *"), {**params, "id": current.id})).mappings().one()
    else:
        r = (await db.execute(text(
            "INSERT INTO site_actions (id, site_key, kind, name, label, description, enabled, "
            "config, secret_enc) VALUES (:id, :s, :k, :n, :l, :d, :e, CAST(:c AS jsonb), :sec) "
            "RETURNING *"), {**params, "id": uuid.uuid4()})).mappings().one()
    invalidate(site_key)
    return _action(r)


async def delete_action(db: AsyncSession, site_key: str, action_id: uuid.UUID) -> bool:
    res = await db.execute(text("DELETE FROM site_actions WHERE id = :id AND site_key = :s"),
                           {"id": action_id, "s": site_key})
    invalidate(site_key)
    return (res.rowcount or 0) > 0


# ---- the agent's view (cached; prompt builders are synchronous) ----------------

_cache: dict[str, tuple[float, list[Action]]] = {}


def invalidate(site_key: str) -> None:
    _cache.pop(site_key, None)


def actions_for(site_key: Optional[str]) -> list[Action]:
    """Enabled actions of a site, as last loaded by ``ensure_actions``."""
    hit = _cache.get(site_key or "")
    return [a for a in hit[1] if a.enabled] if hit else []


async def ensure_actions(db: AsyncSession, site_key: str) -> list[Action]:
    hit = _cache.get(site_key)
    if hit and time.monotonic() - hit[0] < _TTL_S:
        return actions_for(site_key)
    _cache[site_key] = (time.monotonic(), await list_actions(db, site_key))
    return actions_for(site_key)


# ---- runs -------------------------------------------------------------------

def _run(r: Any) -> dict[str, Any]:
    def j(v, default):
        return v if isinstance(v, (dict, list)) else json.loads(v or json.dumps(default))
    iso = lambda v: v.isoformat() if v else None  # noqa: E731
    return {
        "id": str(r["id"]), "action_name": r["action_name"], "kind": r["kind"],
        "session_id": r["session_id"], "status": r["status"], "inputs": j(r["inputs"], {}),
        "summary": j(r["summary"], []), "amount": r["amount"], "currency": r["currency"],
        "result": j(r["result"], {}), "error": r["error"],
        "lead_id": str(r["lead_id"]) if r["lead_id"] else None,
        "created_at": iso(r["created_at"]), "confirmed_at": iso(r["confirmed_at"]),
        "finished_at": iso(r["finished_at"]), "paid_at": iso(r["paid_at"]),
    }


async def propose(db: AsyncSession, action: Action, session_id: str,
                  args: dict[str, Any]) -> dict[str, Any]:
    """Check the agent's arguments and store a run awaiting the visitor.
    Raises InputError (bad arguments) or PermissionError (too many)."""
    inputs = validate_inputs(action.fields, args)
    recent = (await db.execute(text(
        "SELECT count(*) FROM action_runs WHERE site_key = :s AND session_id = :sid "
        "AND created_at > now() - interval '1 hour'"),
        {"s": action.site_key, "sid": session_id})).scalar() or 0
    if recent >= PROPOSALS_PER_SESSION_HOUR:
        raise PermissionError("too many requests in this conversation; try again later")
    amount = currency = None
    if action.kind == "payment_link":
        p = price(action.config, inputs["plan"])
        amount, currency = p["amount"], p["currency"]
    r = (await db.execute(text(
        "INSERT INTO action_runs (id, site_key, action_id, action_name, kind, session_id, "
        "inputs, summary, amount, currency) VALUES (:id, :s, :a, :n, :k, :sid, "
        "CAST(:in AS jsonb), CAST(:sum AS jsonb), :amt, :cur) RETURNING *"), {
        "id": uuid.uuid4(), "s": action.site_key, "a": action.id, "n": action.name,
        "k": action.kind, "sid": session_id, "in": json.dumps(inputs),
        "sum": json.dumps(summary(action.kind, action.fields, action.config, inputs)),
        "amt": amount, "cur": currency})).mappings().one()
    return _run(r)


async def get_run(db: AsyncSession, site_key: str, run_id: uuid.UUID,
                  *, lock: bool = False) -> Optional[dict[str, Any]]:
    r = (await db.execute(text(
        "SELECT * FROM action_runs WHERE id = :id AND site_key = :s"
        + (" FOR UPDATE" if lock else "")), {"id": run_id, "s": site_key})).mappings().first()
    return _run(r) if r else None


async def runs_this_hour(db: AsyncSession, site_key: str, action_name: str) -> int:
    return int((await db.execute(text(
        "SELECT count(*) FROM action_runs WHERE site_key = :s AND action_name = :n "
        "AND status IN ('done', 'paid', 'failed') AND confirmed_at > now() - interval '1 hour'"),
        {"s": site_key, "n": action_name})).scalar() or 0)


async def expired(db: AsyncSession, run: dict[str, Any]) -> bool:
    age = (await db.execute(text(
        "SELECT extract(epoch FROM now() - created_at) FROM action_runs WHERE id = :id"),
        {"id": uuid.UUID(run["id"])})).scalar()
    return float(age or 0) > CONFIRM_WINDOW_S


async def finish(db: AsyncSession, run_id: uuid.UUID, *, status: str,
                 result: Optional[dict] = None, error: Optional[str] = None,
                 external_id: Optional[str] = None, lead_id: Optional[uuid.UUID] = None,
                 confirmed: bool = True) -> dict[str, Any]:
    r = (await db.execute(text(
        "UPDATE action_runs SET status = :st, result = CAST(:res AS jsonb), error = :err, "
        "external_id = COALESCE(:ext, external_id), lead_id = COALESCE(:lead, lead_id), "
        "confirmed_at = CASE WHEN :conf THEN COALESCE(confirmed_at, now()) ELSE confirmed_at END, "
        "finished_at = now() WHERE id = :id RETURNING *"), {
        "id": run_id, "st": status, "res": json.dumps(result or {}), "err": error,
        "ext": external_id, "lead": lead_id, "conf": confirmed})).mappings().one()
    return _run(r)


async def mark_paid(db: AsyncSession, external_id: str, amount_paid: Optional[int]) -> Optional[dict]:
    """A payment link was paid: the run, and its lead, say so. Idempotent."""
    r = (await db.execute(text(
        "UPDATE action_runs SET status = 'paid', paid_at = COALESCE(paid_at, now()) "
        "WHERE external_id = :x AND kind = 'payment_link' AND status IN ('done', 'paid') "
        "RETURNING *"), {"x": external_id})).mappings().first()
    if r is None:
        return None
    if r["lead_id"]:
        await db.execute(text(
            "UPDATE leads SET paid_at = COALESCE(paid_at, now()), "
            "paid_amount = :amt, score = GREATEST(score, 90) WHERE id = :id"),
            {"id": r["lead_id"], "amt": amount_paid or r["amount"]})
    return _run(r)


async def list_runs(db: AsyncSession, site_key: str, *, limit: int = 50,
                    session_id: Optional[str] = None) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT * FROM action_runs WHERE site_key = :s "
        + ("AND session_id = :sid " if session_id else "")
        + "ORDER BY created_at DESC LIMIT :lim"),
        {"s": site_key, "sid": session_id, "lim": limit})).mappings().all()
    return [_run(r) for r in rows]


async def pending_payments(db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
    """Payment links sent in the last week and not paid yet (polled as a
    fallback when the tenant hasn't set up Razorpay's webhook)."""
    rows = (await db.execute(text(
        "SELECT * FROM action_runs WHERE kind = 'payment_link' AND status = 'done' "
        "AND external_id IS NOT NULL AND finished_at > now() - interval '7 days' "
        "ORDER BY finished_at DESC LIMIT :lim"), {"lim": limit})).mappings().all()
    return [{**_run(r), "site_key": r["site_key"], "action_id": r["action_id"],
             "external_id": r["external_id"]} for r in rows]
