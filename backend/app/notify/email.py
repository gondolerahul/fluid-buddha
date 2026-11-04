"""
Email over plain SMTP (M2-0), through an outbox.

Callers never talk to SMTP. They ``enqueue`` a message (a row in
``email_outbox``, committed with their own transaction), and the background
worker (``deliver_due``, run by the job scheduler) sends it:

* a batch of due rows is claimed with ``FOR UPDATE SKIP LOCKED``, so several
  replicas can run the worker without sending the same row twice;
* a failed send is retried with exponential backoff (1, 2, 4 … 32 minutes),
  then marked ``failed`` after ``MAX_ATTEMPTS``;
* a row stuck in ``sending`` (the replica died mid-send) goes back to the
  queue after ``STALE_SENDING``. That is the only case in which a message can
  go out twice — SMTP has no way to make a send idempotent;
* ``idem_key`` makes queuing idempotent (one weekly digest per account and
  week, one invitation per token).

Without ``SMTP_HOST``: in a dev environment the message is written to the log
(so invitation links etc. can be followed locally) and marked sent; anywhere
else ``enqueue`` raises :class:`EmailNotConfigured`, so a missing setup is
loud rather than a silent black hole.

Sent and failed rows are deleted after ``KEEP_DAYS`` (they hold addresses and
bodies).
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
BATCH = 20
STALE_SENDING = "10 minutes"
KEEP_DAYS = 30


class EmailNotConfigured(RuntimeError):
    """No SMTP server is configured outside a dev environment."""


@dataclass
class Email:
    to: str
    subject: str
    text: str
    html: Optional[str] = None
    kind: str = "generic"
    tenant_id: Optional[uuid.UUID] = None
    headers: dict[str, str] = field(default_factory=dict)
    idem_key: Optional[str] = None


def _valid_address(addr: str) -> bool:
    _, a = parseaddr(addr or "")
    return bool(a) and "@" in a and "\n" not in addr and "\r" not in addr


def configured(settings: Optional[Settings] = None) -> bool:
    return bool((settings or get_settings()).smtp_host.strip())


async def enqueue(db: AsyncSession, email: Email) -> Optional[int]:
    """Queue ``email`` (part of the caller's transaction). Returns the outbox
    id, or None when an email with the same ``idem_key`` was already queued."""
    settings = get_settings()
    if not configured(settings) and not settings.is_dev_env:
        raise EmailNotConfigured("Email isn't set up on this server (SMTP_HOST is empty).")
    if not _valid_address(email.to):
        raise ValueError("invalid recipient address")
    if any("\n" in v or "\r" in v for v in (email.subject, *email.headers.values())):
        raise ValueError("header values can't contain line breaks")
    return (await db.execute(text(
        "INSERT INTO email_outbox (kind, tenant_id, to_addr, subject, text_body, html_body, "
        "headers, idem_key) VALUES (:k, :t, :to, :s, :tx, :h, CAST(:hd AS jsonb), :i) "
        "ON CONFLICT (idem_key) DO NOTHING RETURNING id"),
        {"k": email.kind, "t": email.tenant_id, "to": email.to.strip(), "s": email.subject,
         "tx": email.text, "h": email.html, "hd": json.dumps(email.headers),
         "i": email.idem_key})).scalar()


def build_message(row: dict, settings: Settings) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = row["to_addr"]
    msg["Subject"] = row["subject"]
    msg["Date"] = formatdate(localtime=False)
    domain = parseaddr(settings.smtp_from)[1].rpartition("@")[2] or "localhost"
    msg["Message-ID"] = make_msgid(idstring=f"fb{row['id']}", domain=domain)
    headers = row.get("headers") or {}
    if isinstance(headers, str):   # jsonb comes back as text through asyncpg
        headers = json.loads(headers)
    for k, v in headers.items():
        msg[k] = v
    msg.set_content(row["text_body"])
    if row.get("html_body"):
        msg.add_alternative(row["html_body"], subtype="html")
    return msg


def _send_sync(msg: EmailMessage, settings: Settings) -> None:
    mode = settings.smtp_security.strip().lower()
    ctx = ssl.create_default_context()
    if mode == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                                timeout=settings.smtp_timeout_seconds,
                                                context=ctx)
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port,
                              timeout=settings.smtp_timeout_seconds)
    with client:
        client.ehlo()
        if mode == "starttls":
            client.starttls(context=ctx)
            client.ehlo()
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(msg)


async def send_now(row: dict, settings: Optional[Settings] = None) -> None:
    settings = settings or get_settings()
    msg = build_message(row, settings)
    if not configured(settings):
        # Dev only (enqueue refuses elsewhere): show it instead of sending.
        logger.info("email (not sent, no SMTP_HOST) to=%s subject=%r\n%s",
                    row["to_addr"], row["subject"], row["text_body"])
        return
    await asyncio.to_thread(_send_sync, msg, settings)


async def deliver_due(db: AsyncSession) -> dict[str, int]:
    """Send what is due. Returns counts of sent / retried / failed."""
    await db.execute(text(
        "UPDATE email_outbox SET status = 'queued', claimed_at = NULL "
        f"WHERE status = 'sending' AND claimed_at < now() - interval '{STALE_SENDING}'"))
    rows = (await db.execute(text(
        "UPDATE email_outbox SET status = 'sending', claimed_at = now(), "
        "attempts = attempts + 1 WHERE id IN (SELECT id FROM email_outbox "
        "WHERE status = 'queued' AND next_attempt_at <= now() ORDER BY id "
        "LIMIT :n FOR UPDATE SKIP LOCKED) RETURNING *"), {"n": BATCH})).mappings().all()
    await db.commit()   # the claim is visible to other replicas from here on
    counts = {"sent": 0, "retried": 0, "failed": 0}
    for row in rows:
        try:
            await send_now(dict(row))
        except Exception as exc:   # SMTP errors, timeouts, refused recipients
            err = f"{type(exc).__name__}: {exc}"[:500]
            final = row["attempts"] >= MAX_ATTEMPTS
            await db.execute(text(
                "UPDATE email_outbox SET status = :st, last_error = :e, claimed_at = NULL, "
                "next_attempt_at = now() + make_interval(mins => :m) WHERE id = :id"),
                {"st": "failed" if final else "queued", "e": err, "id": row["id"],
                 "m": 2 ** (row["attempts"] - 1)})
            counts["failed" if final else "retried"] += 1
            logger.warning("email %s to %s: attempt %s failed: %s", row["id"], row["to_addr"],
                           row["attempts"], err)
        else:
            await db.execute(text(
                "UPDATE email_outbox SET status = 'sent', sent_at = now(), last_error = NULL, "
                "claimed_at = NULL WHERE id = :id"), {"id": row["id"]})
            counts["sent"] += 1
        await db.commit()
    return counts


async def purge_old(db: AsyncSession) -> int:
    n = (await db.execute(text(
        "DELETE FROM email_outbox WHERE status IN ('sent', 'failed') "
        "AND created_at < now() - make_interval(days => :d)"), {"d": KEEP_DAYS})).rowcount
    await db.commit()
    return n or 0
