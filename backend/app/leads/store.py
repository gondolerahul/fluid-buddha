"""
Leads (WS7): who wants to talk to sales, how hot they are, and what they asked.

A lead comes from the widget's enquiry form (``source='form'``) or from the
agent's ``capture_lead`` tool when a visitor shares their details mid-
conversation (``source='conversation'``). Either way it is linked to the
visitor's conversation, scored by transparent rules, and summarised from the
questions they asked — no LLM sees the contact details on the form path.
"""
from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import secrets as stored
from app.trust.pii import SENSITIVE, redact

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
# A message that shares contact details isn't a question about the product.
_HAS_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}|\[email\]|<email_\d+>", re.I)
_BUYING_RE = re.compile(
    r"\b(pric|cost|quote|demo|trial|buy|purchase|plan|contract|onboard|integrat)", re.I)
_FIELD_MAX = {"name": 200, "email": 320, "company": 200, "phone": 50,
              "message": 4000, "interest": 500}


class LeadError(ValueError):
    """The submitted lead is invalid."""


@dataclass
class LeadIn:
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    interest: Optional[str] = None

    def cleaned(self) -> "LeadIn":
        vals = {k: (str(v).strip()[:_FIELD_MAX[k]] or None) if v is not None else None
                for k, v in self.__dict__.items()}
        email = (vals["email"] or "").lower()
        if not EMAIL_RE.match(email):
            raise LeadError("a valid email address is required")
        vals["email"] = email
        # Card, ID and bank numbers have no place in a lead (WS8).
        for k in ("message", "interest"):
            if vals[k]:
                vals[k] = redact(vals[k], SENSITIVE)
        return LeadIn(**vals)


def score_lead(lead: LeadIn, questions: list[str], persona: Optional[str]) -> int:
    """Transparent 0-100 score (shown in the console next to its reasons):
    contact details given, how much they asked, a known persona, and whether
    any question was about buying (pricing, demo, plans, integration)."""
    score = 20  # a reachable email
    score += 10 * sum(1 for v in (lead.name, lead.company, lead.phone) if v)
    score += min(30, 10 * len(questions))
    if persona:
        score += 10
    if any(_BUYING_RE.search(q) for q in questions) or _BUYING_RE.search(
            f"{lead.message or ''} {lead.interest or ''}"):
        score += 15
    return min(100, score)


def summarize(lead: LeadIn, questions: list[str]) -> str:
    parts = []
    if lead.interest:
        parts.append(f"Interested in: {lead.interest}.")
    if questions:
        recent = questions[-5:]
        parts.append(f"Asked {len(questions)} question{'s' if len(questions) != 1 else ''}: "
                     + "; ".join(q.rstrip("?") + "?" for q in recent))
    if lead.message:
        parts.append(f"Message: {lead.message}")
    return " ".join(parts)


async def _conversation(db: AsyncSession, site_key: str,
                        session_id: Optional[str]) -> tuple[Optional[uuid.UUID], list[str], Optional[str]]:
    if not session_id:
        return None, [], None
    row = (await db.execute(text(
        "SELECT id, persona FROM conversations WHERE site_key = :s AND session_id = :sid"
    ), {"s": site_key, "sid": session_id})).first()
    if row is None:
        return None, [], None
    questions = (await db.execute(text(
        "SELECT question FROM conversation_turns WHERE conversation_id = :c "
        "AND coalesce(intent, '') <> 'greeting' ORDER BY created_at"
    ), {"c": row[0]})).scalars().all()
    return row[0], [q for q in questions if not _HAS_EMAIL.search(q)], row[1]


async def create_lead(
    db: AsyncSession, *, site_key: str, lead: LeadIn, session_id: Optional[str] = None,
    source: str = "form", persona: Optional[str] = None,
) -> dict[str, Any]:
    """Validate, score, summarise and store a lead. The caller commits."""
    lead = lead.cleaned()
    conv_id, questions, conv_persona = await _conversation(db, site_key, session_id)
    persona = persona or conv_persona
    lid = uuid.uuid4()
    row = (await db.execute(text(
        "INSERT INTO leads (id, site_key, session_id, conversation_id, source, name, email, "
        " company, phone, message, interest, persona, score, summary) VALUES "
        "(:id, :s, :sid, :c, :src, :n, :e, :co, :ph, :m, :i, :p, :sc, :sum) "
        "RETURNING *"
    ), {
        "id": lid, "s": site_key, "sid": session_id, "c": conv_id, "src": source,
        "n": lead.name, "e": lead.email, "co": lead.company, "ph": lead.phone,
        "m": lead.message, "i": lead.interest, "p": persona,
        "sc": score_lead(lead, questions, persona), "sum": summarize(lead, questions),
    })).mappings().one()
    return lead_dict(row)


def lead_dict(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]), "site_key": r["site_key"], "source": r["source"],
        "name": r["name"], "email": r["email"], "company": r["company"], "phone": r["phone"],
        "message": r["message"], "interest": r["interest"], "persona": r["persona"],
        "score": r["score"], "summary": r["summary"], "status": r["status"],
        "conversation_id": str(r["conversation_id"]) if r["conversation_id"] else None,
        "delivered_at": r["delivered_at"].isoformat() if r["delivered_at"] else None,
        "delivery_error": r["delivery_error"],
        "created_at": r["created_at"].isoformat(),
        # Paid through a payment action (M2-8), in paise.
        "paid_at": r["paid_at"].isoformat() if r.get("paid_at") else None,
        "paid_amount": r.get("paid_amount"),
        # The conversation's recap link, if the visitor asked for one (M2-6).
        "recap": ({"views": r["recap_views"], "forwards": max(0, (r["recap_viewers"] or 0) - 1),
                   "last_viewed_at": r["recap_last"].isoformat() if r["recap_last"] else None}
                  if r.get("recap_views") is not None else None),
    }


_WITH_RECAP = ("l.*, r.views AS recap_views, r.viewers AS recap_viewers, "
                "r.last_viewed_at AS recap_last FROM leads l "
                "LEFT JOIN recaps r ON r.conversation_id = l.conversation_id")


async def list_leads(db: AsyncSession, site_key: str, *, limit: int = 50,
                     offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    total = (await db.execute(text("SELECT count(*) FROM leads WHERE site_key = :s"),
                              {"s": site_key})).scalar() or 0
    rows = (await db.execute(text(
        f"SELECT {_WITH_RECAP} WHERE l.site_key = :s ORDER BY l.created_at DESC "
        "LIMIT :lim OFFSET :off"), {"s": site_key, "lim": limit, "off": offset})).mappings().all()
    return [lead_dict(r) for r in rows], int(total)


async def get_lead(db: AsyncSession, site_key: str, lead_id: uuid.UUID) -> Optional[dict]:
    row = (await db.execute(text(f"SELECT {_WITH_RECAP} WHERE l.id = :id AND l.site_key = :s"),
                            {"id": lead_id, "s": site_key})).mappings().first()
    return lead_dict(row) if row else None


async def set_status(db: AsyncSession, site_key: str, lead_id: uuid.UUID,
                     status: str) -> Optional[dict]:
    row = (await db.execute(text(
        "UPDATE leads SET status = :st WHERE id = :id AND site_key = :s RETURNING *"
    ), {"st": status, "id": lead_id, "s": site_key})).mappings().first()
    return lead_dict(row) if row else None


async def mark_delivery(db: AsyncSession, lead_id: uuid.UUID, error: Optional[str]) -> None:
    await db.execute(text(
        "UPDATE leads SET delivered_at = CASE WHEN CAST(:e AS text) IS NULL THEN now() "
        "ELSE delivered_at END, delivery_error = CAST(:e AS text) WHERE id = :id"
    ), {"e": error, "id": lead_id})


# ---- integrations ------------------------------------------------------------

def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(24)


# The signing secret and the Slack webhook URL (itself a credential) are stored
# encrypted (M2-11, app/security/secrets.py).
def _seal(value: Optional[str]) -> Optional[str]:
    return stored.encrypt(value) if value else value


def _open(value: Optional[str]) -> Optional[str]:
    if not value or not value.startswith("gAAAAA"):
        return value   # empty, or written before encryption (migration 0024 converts)
    return stored.decrypt(value)


def _readable(row: Any) -> dict[str, Any]:
    out = dict(row)
    for k in ("webhook_secret", "slack_webhook_url"):
        out[k] = _open(out.get(k))
    return out


async def get_integrations(db: AsyncSession, site_key: str) -> dict[str, Any]:
    """The site's integration settings (created with a signing secret on first read)."""
    row = (await db.execute(text(
        "INSERT INTO site_integrations (site_key, webhook_secret) VALUES (:s, :sec) "
        "ON CONFLICT (site_key) DO UPDATE SET site_key = EXCLUDED.site_key "
        "RETURNING webhook_url, webhook_secret, slack_webhook_url, hot_lead_score, cost_alert_usd"
    ), {"s": site_key, "sec": _seal(new_secret())})).mappings().one()
    return _readable(row)


async def slack_webhook(db: AsyncSession, site_key: str) -> Optional[str]:
    raw = (await db.execute(text(
        "SELECT slack_webhook_url FROM site_integrations WHERE site_key = :s"),
        {"s": site_key})).scalar()
    return _open(raw)


async def save_integrations(db: AsyncSession, site_key: str, *, webhook_url: Optional[str],
                            slack_webhook_url: Optional[str], hot_lead_score: int,
                            cost_alert_usd: Optional[float] = None,
                            rotate_secret: bool = False) -> dict[str, Any]:
    from app.analytics.alerts import forget_threshold

    await get_integrations(db, site_key)
    forget_threshold(site_key)
    row = (await db.execute(text(
        "UPDATE site_integrations SET webhook_url = :w, slack_webhook_url = :sl, "
        "hot_lead_score = :h, cost_alert_usd = :c, updated_at = now()"
        + (", webhook_secret = :sec" if rotate_secret else "") +
        " WHERE site_key = :s "
        "RETURNING webhook_url, webhook_secret, slack_webhook_url, hot_lead_score, cost_alert_usd"
    ), {"w": webhook_url, "sl": _seal(slack_webhook_url), "h": hot_lead_score, "c": cost_alert_usd,
        "sec": _seal(new_secret()), "s": site_key})).mappings().one()
    return _readable(row)
