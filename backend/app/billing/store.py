"""
Billing state and rules (WS12).

* **Effective plan.** An account is on its paid plan while Razorpay says the
  subscription is ``authenticated``, ``active`` or ``pending`` (a renewal that
  failed and is being retried). ``halted``, ``cancelled``, ``completed`` and
  ``expired`` fall back to Free. Enterprise is set by hand (status ``manual``).
* **Period.** A paid plan's period is the subscription's current billing
  cycle; Free uses the calendar month (UTC).
* **Conversations** are distinct visitor sessions with at least one answered
  turn in the period, across all of the account's websites, counted from
  ``usage_events`` (which retention and visitor erasure don't delete).
* **Caps.** Free stops answering new conversations once its allowance is used
  (a conversation already under way may finish). Paid plans keep answering;
  the extra conversations of a finished period are added to the Razorpay
  subscription as an add-on and charged with the next invoice.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import plans as catalog
from app.billing.razorpay import Razorpay, RazorpayError

logger = logging.getLogger(__name__)

PAID_STATUSES = ("authenticated", "active", "pending")
LIVE_STATUSES = ("created", *PAID_STATUSES)
# Waiting on Razorpay (payment not yet confirmed, or being retried): the
# console re-reads the subscription from Razorpay on these.
SYNC_STATUSES = ("created", "authenticated", "pending")


class BillingError(ValueError):
    """A request the account can't make (shown to the tenant)."""


@dataclass
class Account:
    tenant_id: uuid.UUID
    plan: str = "free"
    pending_plan: Optional[str] = None
    status: str = "none"
    subscription_id: Optional[str] = None
    current_start: Optional[datetime] = None
    current_end: Optional[datetime] = None
    cancel_at_cycle_end: bool = False

    @property
    def effective_plan(self) -> str:
        if self.status == "manual":
            return self.plan
        return self.plan if self.status in PAID_STATUSES else "free"

    def period(self, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
        now = now or datetime.now(timezone.utc)
        if (self.effective_plan != "free" and self.current_start and self.current_end
                and self.current_start <= now):
            return self.current_start, self.current_end
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start.replace(year=start.year + 1, month=1) if start.month == 12
               else start.replace(month=start.month + 1))
        return start, end


_COLS = ("tenant_id, plan, pending_plan, status, subscription_id, current_start, "
         "current_end, cancel_at_cycle_end")


async def get_account(db: AsyncSession, tenant_id: uuid.UUID) -> Account:
    row = (await db.execute(
        text(f"SELECT {_COLS} FROM tenant_billing WHERE tenant_id = :t"), {"t": tenant_id},
    )).mappings().first()
    return Account(**dict(row)) if row else Account(tenant_id=tenant_id)


async def save_account(db: AsyncSession, a: Account) -> None:
    await db.execute(text(
        f"INSERT INTO tenant_billing ({_COLS}, updated_at) VALUES (:tenant_id, :plan, "
        ":pending_plan, :status, :subscription_id, :current_start, :current_end, "
        ":cancel_at_cycle_end, now()) ON CONFLICT (tenant_id) DO UPDATE SET "
        "plan = :plan, pending_plan = :pending_plan, status = :status, "
        "subscription_id = :subscription_id, current_start = :current_start, "
        "current_end = :current_end, cancel_at_cycle_end = :cancel_at_cycle_end, "
        "updated_at = now()"
    ), a.__dict__)
    await db.commit()
    forget_cap(a.tenant_id)


# ---- usage ---------------------------------------------------------------------

async def conversations(db: AsyncSession, tenant_id: uuid.UUID,
                        start: datetime, end: datetime) -> int:
    return int((await db.execute(text(
        "SELECT count(DISTINCT (u.site_key, u.session_id)) FROM usage_events u "
        "JOIN tenant_websites w ON w.site_key = u.site_key "
        "WHERE w.tenant_id = :t AND u.session_id IS NOT NULL "
        "AND u.created_at >= :s AND u.created_at < :e"
    ), {"t": tenant_id, "s": start, "e": end})).scalar() or 0)


async def usage_by_site(db: AsyncSession, tenant_id: uuid.UUID,
                        start: datetime, end: datetime) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT w.id, w.name, count(DISTINCT u.session_id) AS conversations, "
        "coalesce(sum(u.total_cost), 0) AS cost, count(u.id) AS turns "
        "FROM tenant_websites w LEFT JOIN usage_events u ON u.site_key = w.site_key "
        "AND u.session_id IS NOT NULL AND u.created_at >= :s AND u.created_at < :e "
        "WHERE w.tenant_id = :t GROUP BY w.id, w.name ORDER BY 3 DESC, w.name"
    ), {"t": tenant_id, "s": start, "e": end})).mappings().all()
    out = []
    for r in rows:
        n = int(r["conversations"])
        cost = float(r["cost"])
        out.append({"website_id": str(r["id"]), "name": r["name"], "conversations": n,
                    "turns": int(r["turns"]), "cost_usd": round(cost, 4),
                    "cost_per_conversation_usd": round(cost / n, 4) if n else None})
    return out


# ---- the Free cap, checked on public turns -------------------------------------------

_cap_cache: dict[uuid.UUID, tuple[float, bool]] = {}
_CAP_TTL_S = 60.0


def forget_cap(tenant_id: uuid.UUID) -> None:
    _cap_cache.pop(tenant_id, None)


async def over_plan_limit(db: AsyncSession, site_key: str,
                          session_id: Optional[str] = None) -> bool:
    """True when the site's account has used a hard-capped allowance and this
    turn would start a new conversation."""
    tenant_id = (await db.execute(
        text("SELECT tenant_id FROM tenant_websites WHERE site_key = :k"), {"k": site_key},
    )).scalar()
    if tenant_id is None:
        return False  # built-in demo sites aren't billed
    now = time.monotonic()
    hit = _cap_cache.get(tenant_id)
    if hit and hit[0] > now:
        over = hit[1]
    else:
        acct = await get_account(db, tenant_id)
        p = catalog.plan(acct.effective_plan)
        over = False
        if p.included is not None and p.overage is None:
            start, end = acct.period()
            over = await conversations(db, tenant_id, start, end) >= p.included
        _cap_cache[tenant_id] = (now + _CAP_TTL_S, over)
    if not over or not session_id:
        return over
    # A conversation that already started this period may finish.
    acct = await get_account(db, tenant_id)
    start, _ = acct.period()
    started = (await db.execute(text(
        "SELECT 1 FROM usage_events WHERE site_key = :k AND session_id = :s "
        "AND created_at >= :start LIMIT 1"
    ), {"k": site_key, "s": session_id, "start": start})).scalar()
    return not started


# ---- Razorpay plans, checkout and changes -------------------------------------------------

async def razorpay_plan_id(db: AsyncSession, rzp: Razorpay, plan_key: str) -> str:
    """The Razorpay plan for a catalog plan under this API key, made on first use."""
    p = catalog.plan(plan_key)
    cur = catalog.currency()
    found = (await db.execute(text(
        "SELECT razorpay_plan_id FROM razorpay_plans "
        "WHERE key_id = :k AND plan = :p AND currency = :c AND amount = :a"
    ), {"k": rzp.key_id, "p": p.key, "c": cur, "a": p.price})).scalar()
    if found:
        return found
    created = await rzp.create_plan(
        name=f"Fluid-Buddha {p.name}", amount=p.price, currency=cur,
        description=f"{p.included:,} conversations a month" if p.included else p.name,
    )
    await db.execute(text(
        "INSERT INTO razorpay_plans (key_id, plan, currency, amount, razorpay_plan_id) "
        "VALUES (:k, :p, :c, :a, :id) ON CONFLICT DO NOTHING"
    ), {"k": rzp.key_id, "p": p.key, "c": cur, "a": p.price, "id": created["id"]})
    await db.commit()
    return created["id"]


async def _plan_missing(rzp: Razorpay, plan_id: str) -> bool:
    try:
        await rzp.fetch_plan(plan_id)
        return False
    except RazorpayError as exc:
        return exc.status in (400, 404)


async def _plan_key_for(db: AsyncSession, razorpay_plan_id: Optional[str]) -> Optional[str]:
    if not razorpay_plan_id:
        return None
    return (await db.execute(
        text("SELECT plan FROM razorpay_plans WHERE razorpay_plan_id = :id"),
        {"id": razorpay_plan_id},
    )).scalar()


async def start_checkout(db: AsyncSession, rzp: Razorpay, tenant_id: uuid.UUID,
                         plan_key: str) -> dict:
    p = catalog.catalog().get(plan_key)
    if p is None or plan_key not in catalog.PAID_PLANS or not p.self_serve:
        raise BillingError("That plan can't be bought online.")
    acct = await get_account(db, tenant_id)
    plan_id = await razorpay_plan_id(db, rzp, plan_key)

    if acct.subscription_id and acct.status in PAID_STATUSES:
        if acct.plan == plan_key and not acct.cancel_at_cycle_end:
            raise BillingError(f"You're already on {p.name}.")
        # Upgrades apply now (prorated by Razorpay); downgrades at the cycle end.
        upgrade = p.price > catalog.plan(acct.plan).price
        try:
            await rzp.change_plan(acct.subscription_id, plan_id, now=upgrade)
        except RazorpayError as exc:
            if "upi" in exc.description.lower():
                # Razorpay can't modify a subscription paid by UPI autopay.
                raise BillingError(
                    "Your subscription is paid by UPI Autopay, which Razorpay doesn't let us "
                    "change. Cancel it (you keep your plan to the end of this period), then "
                    "choose the new plan.")
            raise BillingError(f"Razorpay couldn't change the plan: {exc.description}")
        if upgrade:
            acct.plan, acct.pending_plan = plan_key, None
        else:
            acct.pending_plan = plan_key
        acct.cancel_at_cycle_end = False
        await save_account(db, acct)
        return {"action": "changed", "plan": plan_key, "effective": "now" if upgrade else "cycle_end"}

    notes = {"tenant_id": str(tenant_id), "plan": plan_key}
    try:
        sub = await rzp.create_subscription(plan_id=plan_id, notes=notes)
    except RazorpayError as exc:
        # The remembered plan may be gone from Razorpay (deleted, or another
        # account behind the same key id): forget it, make a fresh one, retry.
        if not await _plan_missing(rzp, plan_id):
            raise BillingError(f"Razorpay couldn't start the subscription: {exc.description}")
        await db.execute(text("DELETE FROM razorpay_plans WHERE razorpay_plan_id = :id"),
                         {"id": plan_id})
        await db.commit()
        try:
            sub = await rzp.create_subscription(
                plan_id=await razorpay_plan_id(db, rzp, plan_key), notes=notes)
        except RazorpayError as exc2:
            raise BillingError(f"Razorpay couldn't start the subscription: {exc2.description}")
    acct.subscription_id = sub["id"]
    acct.status = sub.get("status") or "created"
    acct.pending_plan = plan_key
    acct.cancel_at_cycle_end = False
    await save_account(db, acct)
    return {"action": "checkout", "plan": plan_key, "subscription_id": sub["id"],
            "short_url": sub.get("short_url"), "key_id": rzp.key_id}


async def confirm_checkout(db: AsyncSession, rzp: Razorpay, tenant_id: uuid.UUID, *,
                           payment_id: str, subscription_id: str, signature: str) -> Account:
    acct = await get_account(db, tenant_id)
    if subscription_id != acct.subscription_id:
        raise BillingError("That payment isn't for this account's subscription.")
    if not rzp.checkout_signature_ok(payment_id=payment_id, subscription_id=subscription_id,
                                     signature=signature):
        raise BillingError("The payment signature didn't verify.")
    sub = await rzp.fetch_subscription(subscription_id)
    return await apply_subscription(db, acct, sub)


async def cancel(db: AsyncSession, rzp: Razorpay, tenant_id: uuid.UUID) -> Account:
    acct = await get_account(db, tenant_id)
    if not acct.subscription_id or acct.status not in LIVE_STATUSES:
        raise BillingError("There's no subscription to cancel.")
    try:
        await rzp.cancel_subscription(acct.subscription_id, at_cycle_end=acct.status != "created")
    except RazorpayError as exc:
        raise BillingError(f"Razorpay couldn't cancel: {exc.description}")
    if acct.status == "created":   # never paid: drop it outright
        acct.status, acct.pending_plan = "cancelled", None
    else:
        acct.cancel_at_cycle_end = True
    await save_account(db, acct)
    return acct


def _ts(v: Any) -> Optional[datetime]:
    return datetime.fromtimestamp(int(v), tz=timezone.utc) if v else None


async def apply_subscription(db: AsyncSession, acct: Account, sub: dict) -> Account:
    """Bring the account in line with a Razorpay subscription entity."""
    acct.status = sub.get("status") or acct.status
    acct.subscription_id = sub.get("id") or acct.subscription_id
    acct.current_start = _ts(sub.get("current_start")) or acct.current_start
    acct.current_end = _ts(sub.get("current_end")) or acct.current_end
    key = await _plan_key_for(db, sub.get("plan_id"))
    if key and acct.status in PAID_STATUSES:
        # Razorpay keeps the old plan on the subscription until a scheduled
        # downgrade takes effect at the cycle end.
        acct.plan = key
        if acct.pending_plan == key:
            acct.pending_plan = None
    if acct.status in ("cancelled", "completed", "expired"):
        acct.plan, acct.pending_plan, acct.cancel_at_cycle_end = "free", None, False
    await save_account(db, acct)
    return acct


# ---- webhooks and overage -----------------------------------------------------------------------

async def handle_webhook(db: AsyncSession, rzp: Optional[Razorpay], event_id: str,
                         payload: dict) -> str:
    """Apply one verified webhook. Returns what happened (for logs/tests)."""
    event = str(payload.get("event") or "")
    body = payload.get("payload") or {}
    if event == "payment_link.paid":
        link = (body.get("payment_link") or {}).get("entity") or {}
        return "overage_paid" if await mark_link_paid(db, link) else "ignored"
    sub = ((body.get("subscription") or {}).get("entity")) or {}
    if not event.startswith("subscription.") or not sub.get("id"):
        return "ignored"
    tenant_id = (await db.execute(
        text("SELECT tenant_id FROM tenant_billing WHERE subscription_id = :s"), {"s": sub["id"]},
    )).scalar()
    if tenant_id is None:
        note = (sub.get("notes") or {}).get("tenant_id")
        try:
            tenant_id = uuid.UUID(str(note)) if note else None
        except ValueError:
            tenant_id = None
    if tenant_id is None:
        return "unknown_subscription"
    inserted = (await db.execute(text(
        "INSERT INTO billing_events (event_id, event, tenant_id) VALUES (:id, :e, :t) "
        "ON CONFLICT DO NOTHING RETURNING event_id"
    ), {"id": event_id, "e": event, "t": tenant_id})).scalar()
    await db.commit()
    if not inserted:
        return "duplicate"

    acct = await get_account(db, tenant_id)
    before = (acct.effective_plan, acct.current_start, acct.current_end)
    acct = await apply_subscription(db, acct, sub)
    # A new cycle began: bill the conversations over the allowance in the last one.
    if (event == "subscription.charged" and before[1] and before[2]
            and acct.current_start and acct.current_start > before[1]):
        await bill_overage(db, rzp, acct, plan_key=before[0], start=before[1], end=before[2])
    else:
        await charge_pending_overage(db, rzp, acct)  # retry anything left unbilled
    return event


async def bill_overage(db: AsyncSession, rzp: Optional[Razorpay], acct: Account, *,
                       plan_key: str, start: datetime, end: datetime) -> Optional[dict]:
    """Record a finished period's overage (once), then charge it."""
    p = catalog.plan(plan_key)
    used = await conversations(db, acct.tenant_id, start, end)
    extra, amount = catalog.overage_amount(p, used)
    row = (await db.execute(text(
        "INSERT INTO billing_overage (tenant_id, period_start, period_end, plan, conversations, "
        "extra, amount, currency, status) VALUES (:t, :s, :e, :p, :n, :x, :a, :c, :st) "
        "ON CONFLICT DO NOTHING RETURNING tenant_id"
    ), {"t": acct.tenant_id, "s": start, "e": end, "p": p.key, "n": used, "x": extra,
        "a": amount, "c": catalog.currency(), "st": "pending" if amount > 0 else "nothing"})).scalar()
    await db.commit()
    if not row:
        return None  # this period was already recorded
    charged = await charge_pending_overage(db, rzp, acct)
    return charged[0] if charged else {"extra": extra, "amount": amount, "status": "pending"}


async def charge_pending_overage(db: AsyncSession, rzp: Optional[Razorpay],
                                 acct: Account) -> list[dict]:
    """Charge every recorded period not yet billed. An add-on rides on the next
    subscription invoice; Razorpay refuses add-ons on some subscriptions (those
    paid by UPI autopay), and those periods get a payment link instead. Anything
    that still fails stays pending and is retried on the next event."""
    if rzp is None:
        return []
    rows = (await db.execute(text(
        "SELECT period_start, period_end, plan, conversations, extra, amount, currency "
        "FROM billing_overage WHERE tenant_id = :t AND status = 'pending' AND amount > 0 "
        "ORDER BY period_start"
    ), {"t": acct.tenant_id})).mappings().all()
    done = []
    for r in rows:
        p = catalog.plan(r["plan"])
        what = (f"{r['period_start']:%d %b} – {r['period_end']:%d %b %Y}: {r['conversations']:,} "
                f"conversations, {p.included or 0:,} included")
        update: dict = {}
        if acct.subscription_id:
            try:
                addon = await rzp.create_addon(
                    acct.subscription_id, amount=r["amount"], currency=r["currency"],
                    name=f"Extra conversations ({r['extra']:,})", description=what)
                update = {"status": "addon", "addon_id": addon["id"], "error": None}
            except RazorpayError as exc:
                logger.info("add-on refused for tenant %s (%s); sending a payment link",
                            acct.tenant_id, exc.description)
                update = {"error": exc.description}
        if update.get("status") != "addon":
            owner = (await db.execute(text("SELECT email, name FROM tenants WHERE id = :t"),
                                      {"t": acct.tenant_id})).mappings().first()
            try:
                link = await rzp.create_payment_link(
                    amount=r["amount"], currency=r["currency"],
                    description=f"Fluid-Buddha extra conversations — {what}",
                    email=owner["email"], name=owner["name"] or owner["email"],
                    reference_id=f"ovg_{r['period_start']:%Y%m%d}_{acct.tenant_id.hex[:12]}",
                    notes={"tenant_id": str(acct.tenant_id),
                           "period_start": r["period_start"].isoformat()})
                update = {"status": "link", "payment_link_id": link["id"],
                          "payment_link_url": link.get("short_url"), "error": None}
            except RazorpayError as exc:
                logger.error("overage for tenant %s not billed: %s", acct.tenant_id, exc)
                update = {"error": exc.description}
        sets = ", ".join(f"{k} = :{k}" for k in update)
        await db.execute(text(
            f"UPDATE billing_overage SET {sets} WHERE tenant_id = :t AND period_start = :s"
        ), {**update, "t": acct.tenant_id, "s": r["period_start"]})
        await db.commit()
        done.append({"extra": r["extra"], "amount": r["amount"],
                     "status": update.get("status", "pending"),
                     "addon_id": update.get("addon_id"),
                     "payment_link_url": update.get("payment_link_url")})
    return done


async def sync_payment_links(db: AsyncSession, rzp: Razorpay, tenant_id: uuid.UUID) -> None:
    """Ask Razorpay about links still unpaid here, in case the webhook is late
    (or not configured yet)."""
    ids = (await db.execute(text(
        "SELECT payment_link_id FROM billing_overage WHERE tenant_id = :t "
        "AND status = 'link' AND payment_link_id IS NOT NULL LIMIT 5"
    ), {"t": tenant_id})).scalars().all()
    for link_id in ids:
        link = await rzp.fetch_payment_link(link_id)
        if link.get("status") == "paid":
            await mark_link_paid(db, link)


async def mark_link_paid(db: AsyncSession, link: dict) -> bool:
    res = await db.execute(text(
        "UPDATE billing_overage SET status = 'paid' WHERE payment_link_id = :id AND status = 'link'"
    ), {"id": link.get("id")})
    await db.commit()
    return bool(res.rowcount)


async def overage_history(db: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT period_start, period_end, plan, conversations, extra, amount, currency, addon_id, "
        "status, payment_link_url FROM billing_overage WHERE tenant_id = :t "
        "ORDER BY period_start DESC LIMIT 12"
    ), {"t": tenant_id})).mappings().all()
    return [{**dict(r), "period_start": r["period_start"].isoformat(),
             "period_end": r["period_end"].isoformat()} for r in rows]
