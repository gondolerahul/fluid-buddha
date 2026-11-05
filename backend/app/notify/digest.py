"""
The weekly digest (M2-5): one email per account on Monday at 9:00 in the
account's time zone, with the last seven days across its websites —
conversations, leads, top questions, new knowledge gaps, objections,
competitor mentions, A/B test results and model cost.

* The ``weekly_digest`` job checks every few minutes; an account is due once
  its local time is Monday 9:00 or later. ``digest_runs`` (one row per account
  and ISO week) plus the outbox's idempotency key make it once a week, however
  many replicas check. A Monday the server missed entirely is skipped, not
  sent late on Tuesday.
* Recipients: the account's Owners until someone chooses a list (Team page).
  A week with no conversations and no leads sends nothing.
* Every email has a one-click unsubscribe (RFC 8058 ``List-Unsubscribe`` +
  ``List-Unsubscribe-Post``) behind a random per-recipient token; the link
  carries no address. An unsubscribed address is never mailed again, even if
  an admin lists it; only that person can resubscribe, from the console.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.notify import email as email_out
from app.notify import templates as t

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Kolkata"
SEND_HOUR = 9
MAX_RECIPIENTS = 20


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def week_key(local: datetime) -> str:
    y, w, _ = local.isocalendar()
    return f"{y}-W{w:02d}"


def due(now_utc: datetime, tz: str) -> Optional[str]:
    """The ISO week to send for, when it is Monday 9:00+ in ``tz``; else None."""
    try:
        local = now_utc.astimezone(ZoneInfo(tz))
    except (ZoneInfoNotFoundError, ValueError):
        local = now_utc.astimezone(ZoneInfo(DEFAULT_TZ))
    if local.weekday() == 0 and local.hour >= SEND_HOUR:
        return week_key(local)
    return None


# ---- settings ------------------------------------------------------------------------

async def owners(db: AsyncSession, tenant_id: uuid.UUID) -> list[str]:
    rows = (await db.execute(text(
        "SELECT u.email FROM memberships m JOIN users u ON u.id = m.user_id "
        "WHERE m.tenant_id = :t AND m.role = 'owner' ORDER BY m.created_at"),
        {"t": tenant_id})).scalars().all()
    return list(rows)


async def get_settings_for(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Any]:
    row = (await db.execute(text(
        "SELECT enabled, recipients, timezone FROM digest_settings WHERE tenant_id = :t"),
        {"t": tenant_id})).mappings().first()
    unsub = set((await db.execute(text(
        "SELECT email FROM digest_unsubscribes WHERE tenant_id = :t"), {"t": tenant_id})).scalars().all())
    if row is None:
        recipients, enabled, tz, chosen = await owners(db, tenant_id), True, DEFAULT_TZ, False
    else:
        recipients, enabled, tz, chosen = list(row["recipients"]), row["enabled"], row["timezone"], True
    return {
        "enabled": enabled, "timezone": tz, "chosen": chosen,
        "recipients": [{"email": e, "unsubscribed": e.lower() in unsub} for e in recipients],
    }


async def save_settings(db: AsyncSession, tenant_id: uuid.UUID, *, enabled: bool,
                        recipients: list[str], tz: str, own_email: Optional[str] = None) -> dict:
    if not valid_timezone(tz):
        raise ValueError(f"Unknown time zone: {tz}")
    clean: list[str] = []
    for e in recipients:
        e = e.strip().lower()
        if e and e not in clean:
            clean.append(e)
    if len(clean) > MAX_RECIPIENTS:
        raise ValueError(f"Up to {MAX_RECIPIENTS} recipients.")
    await db.execute(text(
        "INSERT INTO digest_settings (tenant_id, enabled, recipients, timezone) VALUES (:t, :e, :r, :z) "
        "ON CONFLICT (tenant_id) DO UPDATE SET enabled = :e, recipients = :r, timezone = :z, "
        "updated_at = now()"), {"t": tenant_id, "e": enabled, "r": clean, "z": tz})
    # Only the person themself can take back their own unsubscribe.
    if own_email and own_email.lower() in clean:
        await db.execute(text("DELETE FROM digest_unsubscribes WHERE tenant_id = :t AND email = :e"),
                         {"t": tenant_id, "e": own_email.lower()})
    await db.commit()
    return await get_settings_for(db, tenant_id)


async def unsubscribe(db: AsyncSession, token: str) -> Optional[str]:
    row = (await db.execute(text("SELECT tenant_id, email FROM digest_tokens WHERE token = :k"),
                            {"k": token})).mappings().first()
    if row is None:
        return None
    await db.execute(text(
        "INSERT INTO digest_unsubscribes (tenant_id, email) VALUES (:t, :e) ON CONFLICT DO NOTHING"),
        {"t": row["tenant_id"], "e": row["email"]})
    await db.commit()
    return row["email"]


async def _token(db: AsyncSession, tenant_id: uuid.UUID, email: str) -> str:
    return (await db.execute(text(
        "INSERT INTO digest_tokens (token, tenant_id, email) VALUES (:k, :t, :e) "
        "ON CONFLICT (tenant_id, email) DO UPDATE SET email = EXCLUDED.email RETURNING token"),
        {"k": secrets.token_urlsafe(24), "t": tenant_id, "e": email})).scalar_one()


# ---- content ---------------------------------------------------------------------------

async def build(db: AsyncSession, tenant_id: uuid.UUID, *, now: Optional[datetime] = None) -> dict:
    """The week's numbers for the account (the seven days before ``now``)."""
    from app.experiments import store as exp_store
    from app.insights.classify import OBJECTION_LABELS

    # The database's clock, not this host's: rows are stamped with now() there.
    now = now or (await db.execute(text("SELECT now()"))).scalar_one()
    since, before = now - timedelta(days=7), now - timedelta(days=14)
    sites = (await db.execute(text(
        "SELECT site_key, name FROM tenant_websites WHERE tenant_id = :t ORDER BY created_at"),
        {"t": tenant_id})).mappings().all()
    keys = [s["site_key"] for s in sites]
    names = {s["site_key"]: s["name"] for s in sites}
    p = {"k": keys, "since": since, "before": before, "now": now}

    def one(sql: str) -> Any:
        return db.execute(text(sql), p)

    conv = (await one(
        "SELECT count(*) FILTER (WHERE started_at >= :since) AS now_, "
        "count(*) FILTER (WHERE started_at < :since) AS prev, "
        "count(*) FILTER (WHERE started_at >= :since AND turns >= 2) AS engaged "
        "FROM conversations WHERE site_key = ANY(:k) AND started_at >= :before AND started_at < :now"
    )).mappings().one()
    leads = (await one(
        "SELECT count(*) FILTER (WHERE created_at >= :since) AS now_, "
        "count(*) FILTER (WHERE created_at < :since) AS prev FROM leads "
        "WHERE site_key = ANY(:k) AND created_at >= :before AND created_at < :now")).mappings().one()
    top = (await one(
        "SELECT (array_agg(question ORDER BY created_at DESC))[1] AS q, count(*) AS n "
        "FROM conversation_turns WHERE site_key = ANY(:k) AND created_at >= :since AND created_at < :now "
        "AND coalesce(intent, '') <> 'greeting' AND question NOT LIKE '(%' "
        "GROUP BY q_norm ORDER BY count(*) DESC LIMIT 5")).mappings().all()
    # A site with no knowledge yet can't answer anything, so its "gaps" are just
    # every question: list it as needing content instead (M2-5 follow-up).
    empty = [r[0] for r in (await one(
        "SELECT w.site_key FROM tenant_websites w WHERE w.site_key = ANY(:k) "
        "AND NOT EXISTS (SELECT 1 FROM tenant_sources s WHERE s.website_id = w.id)")).all()]
    p["full"] = [k for k in keys if k not in empty]
    gaps = (await one(
        "SELECT (array_agg(question ORDER BY created_at DESC))[1] AS q, count(*) AS n "
        "FROM conversation_turns t WHERE site_key = ANY(:full) AND created_at >= :since AND created_at < :now "
        "AND NOT found AND coalesce(intent, '') <> 'greeting' AND question NOT LIKE '(%' "
        "AND NOT EXISTS (SELECT 1 FROM conversation_turns o WHERE o.site_key = t.site_key "
        "AND o.q_norm = t.q_norm AND o.created_at < :since) "
        "GROUP BY q_norm ORDER BY count(*) DESC LIMIT 5")).mappings().all()
    objections = (await one(
        "SELECT x AS k, count(*) AS n FROM conversation_turns t, unnest(t.objections) x "
        "WHERE site_key = ANY(:k) AND created_at >= :since AND created_at < :now "
        "GROUP BY x ORDER BY count(*) DESC LIMIT 5")).mappings().all()
    competitors = (await one(
        "SELECT x AS k, count(*) AS n FROM conversation_turns t, unnest(t.competitors) x "
        "WHERE site_key = ANY(:k) AND created_at >= :since AND created_at < :now "
        "GROUP BY x ORDER BY count(*) DESC LIMIT 5")).mappings().all()
    cost = (await one(
        "SELECT coalesce(sum(total_cost), 0) FROM usage_events "
        "WHERE site_key = ANY(:k) AND created_at >= :since AND created_at < :now")).scalar() or 0.0
    tests = []
    for site_key in keys:
        for row in await exp_store.list_tests(db, site_key, limit=5):
            ended = row["ended_at"] and datetime.fromisoformat(row["ended_at"]) < since
            if ended or datetime.fromisoformat(row["started_at"]) >= now:
                continue
            exp = await exp_store.get(db, site_key, uuid.UUID(row["id"]))
            res = await exp_store.variant_results(db, exp)
            v = res["verdict"]
            win = next((x["label"] for x in res["variants"] if x["key"] == v["winner"]), None)
            label = (f"“{win}” wins" if v["status"] == "winner" else
                     "no difference" if v["status"] == "no_difference" else "still collecting")
            tests.append({"site": names[site_key], "name": row["name"], "status": row["status"],
                          "visitors": row["visitors"], "verdict": label})

    return {
        "since": since.isoformat(), "until": now.isoformat(),
        "sites": [names[k] for k in keys],
        "conversations": int(conv["now_"]), "conversations_prev": int(conv["prev"]),
        "engaged": int(conv["engaged"]),
        "leads": int(leads["now_"]), "leads_prev": int(leads["prev"]),
        "top_questions": [{"question": r["q"], "count": int(r["n"])} for r in top],
        "new_gaps": [{"question": r["q"], "count": int(r["n"])} for r in gaps],
        "sites_without_content": [names[k] for k in empty],
        "objections": [{"type": r["k"], "label": OBJECTION_LABELS.get(r["k"], r["k"]),
                        "count": int(r["n"])} for r in objections],
        "competitors": [{"name": r["k"], "count": int(r["n"])} for r in competitors],
        "tests": tests,
        "cost_usd": round(float(cost), 2),
    }


def _change(now_: int, prev: int) -> str:
    if prev == 0:
        return "new" if now_ else "—"
    d = round((now_ - prev) / prev * 100)
    return f"{'+' if d >= 0 else '−'}{abs(d)}% vs last week"


def render(data: dict, *, account: str, unsubscribe_url: Optional[str] = None) -> dict[str, str]:
    """Subject, text and HTML for one recipient."""
    console = get_settings().console_url.rstrip("/")
    subject = (f"Your week on FluidBuddha: {data['conversations']} conversations, "
               f"{data['leads']} leads")
    head = [
        ("Conversations", f"{data['conversations']} ({_change(data['conversations'], data['conversations_prev'])})"),
        ("Asked 2+ questions", str(data["engaged"])),
        ("Leads", f"{data['leads']} ({_change(data['leads'], data['leads_prev'])})"),
        ("Model cost", f"${data['cost_usd']:.2f}"),
    ]
    sections: list[tuple[str, list[str]]] = [
        ("Top questions", [f"{q['question']} ({q['count']})" for q in data["top_questions"]]),
        ("New questions the agent couldn't answer", [f"{q['question']} ({q['count']})" for q in data["new_gaps"]]),
        ("Websites with no content yet (add pages or documents so the agent can answer)",
         list(data.get("sites_without_content") or [])),
        ("Objections", [f"{o['label']}: {o['count']}" for o in data["objections"]]),
        ("Competitors mentioned", [f"{c['name']}: {c['count']}" for c in data["competitors"]]),
        ("A/B tests", [f"{x['site']} · {x['name']}: {x['verdict']} ({x['visitors']} visitors)"
                       for x in data["tests"]]),
    ]
    sections = [(h, items) for h, items in sections if items]

    lines = [f"{account} — the last 7 days", ""] + [f"{k}: {v}" for k, v in head]
    for h, items in sections:
        lines += ["", h] + [f"- {i}" for i in items]
    lines += ["", f"Open the console: {console}/dashboard"]
    if unsubscribe_url:
        lines += ["", f"Stop these emails: {unsubscribe_url}"]

    body = t.paragraph(f"{account} — the last 7 days across {', '.join(data['sites']) or 'your sites'}.")
    body += t.rows(head)
    for h, items in sections:
        body += f'<h2 style="font-size:15px;margin:18px 0 8px">{t.esc(h)}</h2>' + t.bullets(items)
    body += t.button("Open the console", f"{console}/dashboard")
    footer = "You get this weekly summary as a member of this FluidBuddha account."
    html = t.layout("Your week", body, footer, unsubscribe_url=unsubscribe_url)
    return {"subject": subject, "text": "\n".join(lines), "html": html}


# ---- sending ---------------------------------------------------------------------------

def unsubscribe_url(token: str) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/digest/unsubscribe?t={token}"


async def _account_name(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    row = (await db.execute(text("SELECT name, email FROM tenants WHERE id = :t"),
                            {"t": tenant_id})).mappings().first()
    return (row and (row["name"] or row["email"])) or "Your account"


async def send_for(db: AsyncSession, tenant_id: uuid.UUID, week: Optional[str], *,
                   now: Optional[datetime] = None, only: Optional[str] = None) -> int:
    """Queue the digest for the account's recipients (or just ``only``, for a
    test send). Returns how many were queued."""
    cfg = await get_settings_for(db, tenant_id)
    data = await build(db, tenant_id, now=now)
    if only is None and data["conversations"] == 0 and data["leads"] == 0:
        return 0
    account = await _account_name(db, tenant_id)
    to = [only] if only else [r["email"] for r in cfg["recipients"] if not r["unsubscribed"]]
    sent = 0
    for addr in to:
        token = await _token(db, tenant_id, addr.lower())
        url = unsubscribe_url(token)
        msg = render(data, account=account, unsubscribe_url=url)
        queued = await email_out.enqueue(db, email_out.Email(
            to=addr, subject=msg["subject"], text=msg["text"], html=msg["html"], kind="digest",
            tenant_id=tenant_id,
            headers={"List-Unsubscribe": f"<{url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            idem_key=f"digest:{tenant_id}:{week}:{addr.lower()}" if week else None))
        sent += queued is not None
    return sent


async def send_due(db: AsyncSession, *, now: Optional[datetime] = None,
                   tenant_ids: Optional[list[uuid.UUID]] = None) -> int:
    """Send this week's digest for every account that is due (or only those
    in ``tenant_ids``). Returns how many emails were queued."""
    now = now or datetime.now(timezone.utc)
    only = "WHERE w.tenant_id = ANY(:ids)" if tenant_ids is not None else ""
    tenants = (await db.execute(text(
        "SELECT DISTINCT w.tenant_id, coalesce(d.timezone, :tz) AS tz, coalesce(d.enabled, true) AS on_ "
        f"FROM tenant_websites w LEFT JOIN digest_settings d ON d.tenant_id = w.tenant_id {only}"),
        {"tz": DEFAULT_TZ, "ids": tenant_ids})).mappings().all()
    total = 0
    for row in tenants:
        week = due(now, row["tz"])
        if not row["on_"] or week is None:
            continue
        claimed = (await db.execute(text(
            "INSERT INTO digest_runs (tenant_id, week) VALUES (:t, :w) ON CONFLICT DO NOTHING "
            "RETURNING week"), {"t": row["tenant_id"], "w": week})).scalar()
        if not claimed:
            continue
        try:
            n = await send_for(db, row["tenant_id"], week, now=now)
        except email_out.EmailNotConfigured:
            await db.rollback()
            logger.warning("weekly digest skipped: email isn't configured")
            return total
        await db.execute(text("UPDATE digest_runs SET sent_to = :n WHERE tenant_id = :t AND week = :w"),
                         {"n": n, "t": row["tenant_id"], "w": week})
        await db.commit()
        total += n
    return total
