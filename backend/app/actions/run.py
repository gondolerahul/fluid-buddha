"""
Running a confirmed action (M2-8).

* payment_link — a Razorpay Payment Link on the tenant's own account (their
  key id + key secret), for the amount on their price list. Razorpay emails
  the link too; the run turns ``paid`` from Razorpay's webhook (or a poll).
* quote_request — a lead (source ``quote``) delivered like any lead (signed
  webhook, Slack if hot) and emailed to the site's owners.
* trial — a signed POST to the tenant's backend, which answers with a login
  link for the visitor.
* meeting_link — the tenant's booking page with the visitor's details filled
  in (Calendly / Cal.com query parameters). No outbound call.
* webhook — a signed POST of the inputs to the tenant's endpoint; its JSON
  ``message`` (if any) is shown to the visitor.

Outbound calls get the SSRF checks lead delivery uses (public addresses only,
no redirects, no proxy env), carry ``X-FluidBuddha-Signature`` and an
idempotency key (the run id), and are made once (no retry: a trial must not
be created twice). Tests swap ``_transport`` / ``_razorpay_transport``.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import httpx

from app.actions import store
from app.actions.fields import price, rupees
from app.billing.razorpay import Razorpay, RazorpayError
from app.config import get_settings
from app.leads.delivery import sign
from app.tenancy.url_fetch import UnsafeURLError, check_resolved, check_url

logger = logging.getLogger(__name__)

TIMEOUT_S = 10.0
_transport: Optional[httpx.AsyncBaseTransport] = None
_razorpay_transport: Optional[httpx.AsyncBaseTransport] = None


class ActionFailed(RuntimeError):
    """The action ran but didn't work; the message is safe to show the visitor."""


def razorpay_for(action: store.Action, secret: dict[str, str]) -> Razorpay:
    return Razorpay(action.config["key_id"], secret.get("key_secret", ""),
                    transport=_razorpay_transport, base_url=get_settings().razorpay_api_base)


async def _post_signed(url: str, payload: dict[str, Any], secret: str, event: str,
                       run_id: str) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":"), default=str).encode()
    try:
        host, port = check_url(url)
        if _transport is None:
            await check_resolved(host, port)
        async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=False, trust_env=False,
                                     transport=_transport) as client:
            resp = await client.post(url, content=body, headers={
                "Content-Type": "application/json", "X-FluidBuddha-Event": event,
                "X-FluidBuddha-Signature": sign(secret, body),
                "Idempotency-Key": run_id,
            })
    except UnsafeURLError as exc:
        raise ActionFailed(f"the endpoint isn't allowed ({exc})")
    except httpx.HTTPError as exc:
        raise ActionFailed(f"couldn't reach the endpoint ({type(exc).__name__})")
    if resp.status_code >= 300:
        raise ActionFailed(f"the endpoint answered {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _https_or_none(v: Any) -> Optional[str]:
    v = str(v or "").strip()
    return v if v.startswith("https://") and len(v) <= 1000 and " " not in v else None


def meeting_url(config: dict[str, Any], inputs: dict[str, Any]) -> str:
    """The booking page with the visitor's details as query parameters."""
    parts = urlsplit(config["booking_url"])
    q = dict(parse_qsl(parts.query))
    style = config.get("style") or "plain"
    q["name"] = inputs.get("name") or ""
    q["email"] = inputs.get("email") or ""
    topic = inputs.get("topic") or ""
    if topic:
        q["a1" if style == "calendly" else "notes" if style == "cal" else "topic"] = topic
    return urlunsplit(parts._replace(query=urlencode({k: v for k, v in q.items() if v})))


async def _lead(db, action: store.Action, run: dict[str, Any], *, source: str,
                interest: str, message: Optional[str] = None) -> Optional[dict[str, Any]]:
    """The visitor as a lead (an email is an input of every built-in kind)."""
    from app.leads.store import LeadError, LeadIn, create_lead
    inputs = run["inputs"]
    if not inputs.get("email"):
        return None
    try:
        return await create_lead(db, site_key=action.site_key, lead=LeadIn(
            email=inputs["email"], name=inputs.get("name"), company=inputs.get("company"),
            interest=interest, message=message), session_id=run["session_id"], source=source)
    except LeadError:
        return None


async def execute(db, action: store.Action, run: dict[str, Any]) -> dict[str, Any]:
    """Run a confirmed action. Returns {"result", "external_id", "lead"}; raises
    ActionFailed. The caller records it on the run (and commits)."""
    inputs = run["inputs"]
    secret = await store.secrets_of(db, action.id)
    if action.kind == "payment_link":
        p = price(action.config, inputs["plan"])
        if p is None or p["amount"] != run["amount"]:
            raise ActionFailed("that plan is no longer on the price list")
        try:
            link = await razorpay_for(action, secret).create_payment_link(
                amount=p["amount"], currency=p["currency"], description=p["label"][:200],
                email=inputs["email"], name=inputs.get("name") or inputs["email"],
                reference_id=run["id"].replace("-", "")[:40],
                notes={"fluidbuddha_run": run["id"], "plan": p["key"]})
        except RazorpayError as exc:
            raise ActionFailed(f"Razorpay: {exc.description}")
        except httpx.HTTPError:
            raise ActionFailed("couldn't reach Razorpay")
        url = _https_or_none(link.get("short_url"))
        if not url or not link.get("id"):
            raise ActionFailed("Razorpay didn't return a payment link")
        lead = await _lead(db, action, run, source="payment",
                           interest=f"{p['label']} ({rupees(p['amount'])})")
        return {"result": {"url": url, "message": f"Payment link for {p['label']}: {rupees(p['amount'])}."},
                "external_id": link["id"], "lead": lead}

    if action.kind == "quote_request":
        details = inputs.get("details") or ""
        if inputs.get("quantity") is not None:
            details += f" (quantity: {inputs['quantity']})"
        lead = await _lead(db, action, run, source="quote", interest=action.label, message=details)
        return {"result": {"message": "Quote request sent. The team will reply by email."},
                "external_id": None, "lead": lead}

    if action.kind == "trial":
        data = await _post_signed(action.config["url"], {
            "event": "trial.requested", "run_id": run["id"], "site": action.site_key,
            "visitor": {k: inputs.get(k) for k in ("email", "name", "company")}},
            secret.get("signing_secret", ""), "trial.requested", run["id"])
        login = _https_or_none(data.get("login_url"))
        if not login:
            raise ActionFailed("the trial was not created (no login link came back)")
        lead = await _lead(db, action, run, source="trial", interest=action.label)
        return {"result": {"url": login, "message": "Your trial is ready."},
                "external_id": None, "lead": lead}

    if action.kind == "meeting_link":
        lead = await _lead(db, action, run, source="meeting", interest=action.label)
        return {"result": {"url": meeting_url(action.config, inputs),
                           "message": "Pick a time that suits you."},
                "external_id": None, "lead": lead}

    data = await _post_signed(action.config["url"], {
        "event": "action.run", "action": action.name, "run_id": run["id"],
        "site": action.site_key, "inputs": inputs},
        secret.get("signing_secret", ""), "action.run", run["id"])
    msg = data.get("message")
    return {"result": {"message": str(msg)[:300] if isinstance(msg, str) and msg.strip() else "Done.",
                       **({"url": u} if (u := _https_or_none(data.get("url"))) else {})},
            "external_id": None, "lead": None}


async def confirm(db, site_key: str, session_id: str, run_id: uuid.UUID) -> dict[str, Any]:
    """The visitor confirmed: check, run, record. Commits. Raises
    LookupError (no such run), PermissionError (not allowed now)."""
    run = await store.get_run(db, site_key, run_id, lock=True)
    if run is None or run["session_id"] != session_id:
        raise LookupError("no such request")
    if run["status"] != "proposed":
        return run                          # already handled (double click)
    if await store.expired(db, run):
        run = await store.finish(db, run_id, status="expired", confirmed=False)
        await db.commit()
        raise PermissionError("this request expired; ask again")
    action = next((a for a in await store.list_actions(db, site_key)
                   if a.name == run["action_name"] and a.enabled), None)
    if action is None:
        await store.finish(db, run_id, status="failed", error="action switched off", confirmed=False)
        await db.commit()
        raise PermissionError("this action isn't available any more")
    if await store.runs_this_hour(db, site_key, action.name) >= action.config.get("max_per_hour", 20):
        raise PermissionError("this is busy right now; please try again in a while")
    try:
        out = await execute(db, action, run)
    except ActionFailed as exc:
        run = await store.finish(db, run_id, status="failed", error=str(exc)[:300])
        await db.commit()
        logger.info("action %s failed for site=%s: %s", action.name, site_key, exc)
        return run
    lead = out.get("lead")
    run = await store.finish(db, run_id, status="done", result=out["result"],
                             external_id=out.get("external_id"),
                             lead_id=uuid.UUID(lead["id"]) if lead else None)
    await db.commit()
    if lead is not None:
        from app.leads.delivery import deliver_lead
        await deliver_lead(lead)
    if action.kind == "quote_request":
        await _email_owners(site_key, action, run)
    return run


async def _email_owners(site_key: str, action: store.Action, run: dict[str, Any]) -> None:
    """A quote request also goes to the site's owners by email (best-effort)."""
    from sqlalchemy import text as sql

    from app.db import session_scope
    from app.notify import email as email_out, templates
    from app.notify.digest import owners
    try:
        async with session_scope() as db:
            tid = (await db.execute(sql("SELECT tenant_id FROM tenant_websites WHERE site_key = :s"),
                                    {"s": site_key})).scalar()
            if tid is None:
                return
            pairs = [(line["label"], line["value"]) for line in run["summary"]]
            console = get_settings().console_url.rstrip("/")
            html = templates.layout(f"Quote request: {action.label}", templates.rows(pairs)
                                    + templates.button("Open leads", f"{console}/dashboard"))
            for to in await owners(db, tid):
                await email_out.enqueue(db, email_out.Email(
                    to=to, subject=f"Quote request from {run['inputs'].get('email', 'a visitor')}",
                    text="\n".join(f"{k}: {v}" for k, v in pairs), html=html, kind="quote_request",
                    tenant_id=tid, idem_key=f"quote:{run['id']}:{to}"))
            await db.commit()
    except Exception as exc:
        logger.warning("quote email for %s not queued: %s", run["id"], exc)
