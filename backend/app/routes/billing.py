"""
Billing API (WS12), with Razorpay.

Console (the signed-in account):

    GET  /tenant/billing            plan, period, usage vs allowance, per-site cost
    POST /tenant/billing/checkout   {plan} → a Razorpay subscription to pay in Checkout,
                                    or an in-place plan change if already subscribed
    POST /tenant/billing/verify     Checkout's {razorpay_payment_id,
                                    razorpay_subscription_id, razorpay_signature}
    POST /tenant/billing/cancel     at the end of the current cycle

Razorpay:

    POST /billing/razorpay/webhook  signed with RAZORPAY_WEBHOOK_SECRET; each
                                    event is applied once (X-Razorpay-Event-Id)
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import current_tenant
from app.billing import plans as catalog
from app.billing import store as billing
from app.billing.razorpay import client_from_settings, webhook_signature_ok
from app.config import get_settings
from app.db import get_session, session_scope
from app.tenancy import store

logger = logging.getLogger(__name__)

admin = APIRouter(prefix="/tenant/billing", tags=["billing"])
webhooks = APIRouter(prefix="/billing", tags=["billing"])


def _razorpay():
    rzp = client_from_settings(get_settings())
    if rzp is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Payments aren't set up on this server yet.")
    return rzp


async def _summary(db: AsyncSession, acct: billing.Account) -> dict:
    start, end = acct.period()
    p = catalog.plan(acct.effective_plan)
    used = await billing.conversations(db, acct.tenant_id, start, end)
    extra, amount = catalog.overage_amount(p, used)
    settings = get_settings()
    return {
        "plan": acct.effective_plan,
        "subscribed_plan": acct.plan,
        "pending_plan": acct.pending_plan,
        "status": acct.status,
        "cancel_at_cycle_end": acct.cancel_at_cycle_end,
        "currency": catalog.currency(),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "usage": {
            "conversations": used,
            "included": p.included,
            "extra": extra,
            "overage_amount": amount,
            "capped": p.included is not None and p.overage is None,
            "limit_reached": p.overage is None and p.included is not None and used >= p.included,
        },
        "sites": await billing.usage_by_site(db, acct.tenant_id, start, end),
        "overage_history": await billing.overage_history(db, acct.tenant_id),
        "catalog": [pl.to_dict() for pl in catalog.catalog().values()],
        "checkout_enabled": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
        "key_id": settings.razorpay_key_id or None,
    }


@admin.get("")
async def get_billing(
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await _summary(db, await billing.get_account(db, tenant.id))


class CheckoutRequest(BaseModel):
    plan: str = Field(..., pattern="^(growth|scale)$")


@admin.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        result = await billing.start_checkout(db, _razorpay(), tenant.id, body.plan)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    # Prefill Razorpay Checkout with the account's email.
    return {**result, "email": tenant.email, "name": tenant.name or ""}


class VerifyRequest(BaseModel):
    razorpay_payment_id: str = Field(..., min_length=1, max_length=64)
    razorpay_subscription_id: str = Field(..., min_length=1, max_length=64)
    razorpay_signature: str = Field(..., min_length=1, max_length=256)


@admin.post("/verify")
async def verify(
    body: VerifyRequest,
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        acct = await billing.confirm_checkout(
            db, _razorpay(), tenant.id, payment_id=body.razorpay_payment_id,
            subscription_id=body.razorpay_subscription_id, signature=body.razorpay_signature)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return await _summary(db, acct)


@admin.post("/cancel")
async def cancel(
    tenant: store.Tenant = Depends(current_tenant),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        acct = await billing.cancel(db, _razorpay(), tenant.id)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return await _summary(db, acct)


@webhooks.post("/razorpay/webhook")
async def razorpay_webhook(request: Request) -> dict:
    settings = get_settings()
    body = await request.body()
    if not webhook_signature_ok(body, request.headers.get("x-razorpay-signature"),
                                settings.razorpay_webhook_secret):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Body must be JSON")
    # Razorpay sends a unique id per event; fall back to a hash of the body.
    event_id = (request.headers.get("x-razorpay-event-id")
                or hashlib.sha256(body).hexdigest())[:128]
    async with session_scope() as db:
        outcome = await billing.handle_webhook(db, client_from_settings(settings),
                                               event_id, payload)
    logger.info("razorpay webhook %s: %s", payload.get("event"), outcome)
    return {"ok": True, "outcome": outcome,
            "at": datetime.now(timezone.utc).isoformat()}
