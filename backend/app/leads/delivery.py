"""
Outbound lead delivery (WS7): a signed webhook (Zapier, Make, a CRM, your own
endpoint) and a Slack alert for hot leads.

Webhook requests carry ``X-FluidBuddha-Signature: t=<unix>,v1=<hex>`` where
``v1 = HMAC-SHA256(secret, f"{t}.{body}")`` — verify it, and reject stale ``t``,
to know a request is genuine and fresh. Targets get the same SSRF checks as URL
sources: public addresses only, no redirects, no proxy env.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.tenancy.url_fetch import UnsafeURLError, check_resolved, check_url

logger = logging.getLogger(__name__)

SLACK_PREFIX = "https://hooks.slack.com/"
TIMEOUT_S = 5.0
RETRY_DELAYS = (0.5, 1.5)   # between the 3 attempts; tests set these to 0


def validate_webhook_url(url: str) -> str:
    """Shape check when the tenant saves a webhook URL (https outside dev)."""
    url = (url or "").strip()
    check_url(url)
    if not url.startswith("https://") and not get_settings().is_dev_env:
        raise UnsafeURLError("webhook URLs must use https")
    return url


def validate_slack_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(SLACK_PREFIX):
        raise UnsafeURLError(f"Slack incoming-webhook URLs start with {SLACK_PREFIX}")
    return url


def sign(secret: str, body: bytes, ts: Optional[int] = None) -> str:
    ts = int(time.time()) if ts is None else ts
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


async def _post(url: str, body: bytes, headers: dict[str, str],
                transport: Optional[httpx.AsyncBaseTransport]) -> None:
    host, port = check_url(url)
    if transport is None:   # a test transport never touches DNS
        await check_resolved(host, port)
    last: Exception | None = None
    for attempt, delay in enumerate((*RETRY_DELAYS, None)):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False,
                                         trust_env=False, transport=transport) as client:
                resp = await client.post(url, content=body, headers=headers)
            if resp.status_code < 300:
                return
            last = RuntimeError(f"HTTP {resp.status_code}")
            if resp.status_code < 500 and resp.status_code != 429:
                break   # the receiver rejected it; retrying won't help
        except httpx.HTTPError as exc:
            last = exc
        if delay is not None:
            await asyncio.sleep(delay)
    raise RuntimeError(f"delivery failed: {last}")


def _slack_text(lead: dict[str, Any]) -> str:
    who = lead.get("name") or lead["email"]
    at = f" at {lead['company']}" if lead.get("company") else ""
    return (f"Hot lead (score {lead['score']}): {who}{at} <mailto:{lead['email']}|{lead['email']}>\n"
            f"{(lead.get('summary') or '')[:400]}")


async def deliver_lead(lead: dict[str, Any], *,
                       transport: Optional[httpx.AsyncBaseTransport] = None) -> Optional[str]:
    """Send ``lead`` to the site's webhook and (if hot) Slack; record the outcome
    on the lead. Returns the error, if any. Never raises."""
    from app.db import session_scope
    from app.leads.store import get_integrations, mark_delivery

    errors: list[str] = []
    try:
        async with session_scope() as db:
            cfg = await get_integrations(db, lead["site_key"])
        if cfg["webhook_url"]:
            body = json.dumps({"event": "lead.created", "lead": lead},
                              separators=(",", ":")).encode()
            try:
                await _post(cfg["webhook_url"], body, {
                    "Content-Type": "application/json",
                    "X-FluidBuddha-Event": "lead.created",
                    "X-FluidBuddha-Signature": sign(cfg["webhook_secret"], body),
                }, transport)
            except (UnsafeURLError, RuntimeError) as exc:
                errors.append(f"webhook: {exc}")
        if cfg["slack_webhook_url"] and lead["score"] >= cfg["hot_lead_score"]:
            body = json.dumps({"text": _slack_text(lead)}).encode()
            try:
                await _post(cfg["slack_webhook_url"], body,
                            {"Content-Type": "application/json"}, transport)
            except (UnsafeURLError, RuntimeError) as exc:
                errors.append(f"slack: {exc}")
        if cfg["webhook_url"] or cfg["slack_webhook_url"]:
            async with session_scope() as db:
                await mark_delivery(db, uuid.UUID(lead["id"]), "; ".join(errors) or None)
    except Exception as exc:   # delivery must never break the visitor's request
        logger.warning("lead delivery failed for %s: %s", lead.get("id"), exc)
        errors.append(str(exc))
    if errors:
        logger.warning("lead %s delivery errors: %s", lead.get("id"), errors)
    return "; ".join(errors) or None
