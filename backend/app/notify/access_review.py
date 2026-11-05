"""
Quarterly access review (M2-11, SOC 2 CC6.2/CC6.3).

At the start of each quarter every account's Owners and Admins get one email:
who can get in, with what role, who hasn't signed in for 90 days, who has no
two-factor, and pending invitations — with a link to the Team page, where the
full list downloads as CSV (``/tenant/team/access-review.csv``) and access is
changed. Once per account per quarter (the outbox's idempotency key).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.notify import email as mailer
from app.notify import templates

logger = logging.getLogger(__name__)

INACTIVE_DAYS = 90


def quarter_of(now: datetime) -> str:
    return f"{now.year}-Q{(now.month - 1) // 3 + 1}"


async def summary(db: AsyncSession, tenant_id) -> dict:
    rows = (await db.execute(text(
        "SELECT u.email, m.role, u.last_login_at, u.totp_enabled_at IS NOT NULL AS mfa, "
        "u.password_hash IS NOT NULL AS has_password FROM memberships m "
        "JOIN users u ON u.id = m.user_id WHERE m.tenant_id = :t ORDER BY u.email"),
        {"t": tenant_id})).mappings().all()
    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DAYS)
    pending = (await db.execute(text(
        "SELECT count(*) FROM invitations WHERE tenant_id = :t AND accepted_at IS NULL "
        "AND revoked_at IS NULL AND expires_at > now()"), {"t": tenant_id})).scalar() or 0
    return {
        "members": len(rows),
        "by_role": {r: sum(1 for x in rows if x["role"] == r) for r in ("owner", "admin", "editor", "viewer")},
        "inactive": [x["email"] for x in rows if not x["last_login_at"] or x["last_login_at"] < cutoff],
        "no_mfa": [x["email"] for x in rows if x["has_password"] and not x["mfa"]],
        "pending_invitations": pending,
    }


def _email(to: str, account: str, quarter: str, s: dict, link: str, tenant_id) -> mailer.Email:
    lines = [f"Access review for {account}, {quarter}.", "",
             f"{s['members']} people can sign in: " + ", ".join(
                 f"{n} {r}{'s' if n != 1 else ''}" for r, n in s["by_role"].items() if n) + ".",
             f"Not signed in for {INACTIVE_DAYS} days: " + (", ".join(s["inactive"]) or "nobody") + ".",
             "Password sign-in without two-factor: " + (", ".join(s["no_mfa"]) or "nobody") + ".",
             f"Pending invitations: {s['pending_invitations']}.", "",
             "Check that everyone still needs their access and role, remove anyone who doesn't, "
             f"and keep the downloaded list as your record: {link}"]
    body = (templates.paragraph(lines[0])
            + templates.paragraph(lines[2]) + templates.paragraph(lines[3])
            + templates.paragraph(lines[4]) + templates.paragraph(lines[5])
            + templates.paragraph("Check that everyone still needs their access and role, remove "
                                  "anyone who doesn't, and keep the downloaded list as your record.")
            + templates.button("Open the Team page", link))
    return mailer.Email(to=to, subject=f"Quarterly access review: {account} ({quarter})",
                        text="\n".join(lines), html=templates.layout("Quarterly access review", body),
                        kind="access_review", tenant_id=tenant_id,
                        idem_key=f"access-review:{tenant_id}:{quarter}:{to.lower()}")


async def send_due(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Queue this quarter's review for every account not yet sent one. Returns
    how many emails were queued."""
    now = now or datetime.now(timezone.utc)
    quarter = quarter_of(now)
    link = f"{get_settings().console_url.rstrip('/')}/team#access-review"
    tenants = (await db.execute(text(
        "SELECT t.id, COALESCE(t.name, t.email) AS account FROM tenants t "
        "WHERE NOT EXISTS (SELECT 1 FROM email_outbox o WHERE o.tenant_id = t.id "
        "  AND o.kind = 'access_review' AND o.idem_key LIKE :q)"),
        {"q": f"access-review:%:{quarter}:%"})).mappings().all()
    queued = 0
    for t in tenants:
        recipients = (await db.execute(text(
            "SELECT u.email FROM memberships m JOIN users u ON u.id = m.user_id "
            "WHERE m.tenant_id = :t AND m.role IN ('owner', 'admin')"), {"t": t["id"]})).scalars().all()
        if not recipients:
            continue
        s = await summary(db, t["id"])
        for to in recipients:
            try:
                if await mailer.enqueue(db, _email(to, t["account"], quarter, s, link, t["id"])):
                    queued += 1
            except mailer.EmailNotConfigured:
                return queued
            except ValueError:
                logger.warning("access review: skipped an invalid address in account %s", t["id"])
    await db.commit()
    return queued
