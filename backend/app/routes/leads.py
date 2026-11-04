"""
Leads (WS7).

- ``POST /leads`` — public, widget-keyed: the enquiry form posts here directly
  (contact details never pass through the LLM). Rate-limited per site.
- ``/tenant/websites/{id}/leads`` — the tenant's leads, with status updates.
- ``/tenant/websites/{id}/integrations`` — signed webhook + Slack alert setup,
  and a test send.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, session_scope
from app.leads import delivery
from app.leads import store as leads
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.tenancy.url_fetch import UnsafeURLError
from app.transport import guard

public = APIRouter(tags=["leads"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["leads"])

# Form submissions per site per minute (separate from conversation turns).
LEAD_RATE_PER_MIN = 20
_KNOWN = ("email", "name", "company", "phone", "message", "interest")


class LeadRequest(BaseModel):
    key: Optional[str] = None
    site: Optional[str] = None
    session_id: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    interest: Optional[str] = None
    # Raw form fields (the generated enquiry form); known names are mapped,
    # anything else is appended to the message.
    values: dict[str, str] = Field(default_factory=dict, max_length=20)

    def to_lead(self) -> leads.LeadIn:
        vals = {k.lower(): v for k, v in self.values.items()}
        get = lambda f: getattr(self, f) or vals.get(f)  # noqa: E731
        extra = [f"{k}: {v}" for k, v in vals.items() if k not in _KNOWN and v]
        message = "\n".join(filter(None, [get("message"), *extra])) or None
        return leads.LeadIn(email=get("email") or "", name=get("name"), company=get("company"),
                            phone=get("phone"), message=message, interest=get("interest"))


@public.post("/leads", status_code=status.HTTP_201_CREATED)
async def submit_lead(body: LeadRequest, request: Request, background: BackgroundTasks) -> dict:
    async with session_scope() as db:
        try:
            resolved = await resolve_public_site(
                db, key=body.key, site=body.site, intelligence=None,
                origin=request.headers.get("origin"))
        except PublicAccessError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
        if not guard._limiter.allow(f"leads:{resolved.site_key}", LEAD_RATE_PER_MIN):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
        try:
            lead = await leads.create_lead(db, site_key=resolved.site_key, lead=body.to_lead(),
                                           session_id=body.session_id, source="form")
        except leads.LeadError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    background.add_task(delivery.deliver_lead, lead)
    return {"ok": True, "id": lead["id"]}


# ---- admin ------------------------------------------------------------------

@admin.get("/leads")
async def list_leads(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    site: store.Website = Depends(owned_website), db: AsyncSession = Depends(get_session),
) -> dict:
    items, total = await leads.list_leads(db, site.site_key, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


class LeadStatus(BaseModel):
    status: Literal["new", "contacted", "qualified", "won", "lost"]


@admin.patch("/leads/{lead_id}")
async def update_lead(
    lead_id: uuid.UUID, body: LeadStatus,
    site: store.Website = Depends(owned_website), db: AsyncSession = Depends(get_session),
) -> dict:
    lead = await leads.set_status(db, site.site_key, lead_id, body.status)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


class IntegrationsIn(BaseModel):
    webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    hot_lead_score: int = Field(60, ge=0, le=100)
    # Alert (Slack + console) when the site's AI cost for the day passes this, in USD.
    cost_alert_usd: Optional[float] = Field(None, gt=0, le=1_000_000)
    rotate_secret: bool = False

    @field_validator("webhook_url")
    @classmethod
    def _webhook(cls, v: Optional[str]) -> Optional[str]:
        return delivery.validate_webhook_url(v) if v and v.strip() else None

    @field_validator("slack_webhook_url")
    @classmethod
    def _slack(cls, v: Optional[str]) -> Optional[str]:
        return delivery.validate_slack_url(v) if v and v.strip() else None


@admin.get("/integrations")
async def get_integrations(
    site: store.Website = Depends(owned_website), db: AsyncSession = Depends(get_session),
) -> dict:
    return await leads.get_integrations(db, site.site_key)


@admin.put("/integrations")
async def put_integrations(
    body: IntegrationsIn,
    site: store.Website = Depends(owned_website), db: AsyncSession = Depends(get_session),
) -> dict:
    return await leads.save_integrations(
        db, site.site_key, webhook_url=body.webhook_url,
        slack_webhook_url=body.slack_webhook_url, hot_lead_score=body.hot_lead_score,
        cost_alert_usd=body.cost_alert_usd, rotate_secret=body.rotate_secret)


@admin.post("/integrations/test")
async def test_integrations(site: store.Website = Depends(owned_website)) -> dict:
    """Send a sample lead (score 100, so Slack fires too) and report the outcome."""
    sample = {
        "id": str(uuid.uuid4()), "site_key": site.site_key, "source": "test",
        "name": "Test Lead", "email": "test.lead@example.com", "company": "Example Co",
        "phone": None, "message": "This is a test from the console.", "interest": None,
        "persona": None, "score": 100, "summary": "A test delivery from the console.",
        "status": "new", "conversation_id": None, "delivered_at": None,
        "delivery_error": None, "created_at": None,
    }
    try:
        error = await delivery.deliver_lead(sample)
    except UnsafeURLError as exc:   # defensive; deliver_lead reports, never raises
        error = str(exc)
    return {"ok": error is None, "error": error}
