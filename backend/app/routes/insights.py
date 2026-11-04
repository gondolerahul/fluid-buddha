"""
Insights v1 (WS10): what visitors ask, what the agent couldn't answer, and the
transcripts behind it. v2 (M2-5): objections, competitor mentions, feature
requests (which can be sent on to the product team) and buying signals.
"""
from __future__ import annotations

import json
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.insights import store as insights
from app.leads import delivery
from app.leads import store as leads_store
from app.notify import email as email_out
from app.notify import templates
from app.tenancy.url_fetch import UnsafeURLError
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["insights"])


@router.get("/insights")
async def get_insights(
    days: int = Query(30, ge=1, le=365),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await insights.summary(db, site.site_key, days)


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    items, total = await insights.list_conversations(
        db, site.site_key, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    conv = await insights.get_conversation(db, site.site_key, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


# ---- Insights v2 (M2-5) ---------------------------------------------------------------

@router.get("/insights/signals")
async def get_signals(
    days: int = Query(30, ge=1, le=365),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Objections, competitor mentions, grouped feature requests, buying signals."""
    return await insights.signals(db, site.site_key, days)


class SendRequest(BaseModel):
    channel: Literal["slack", "webhook", "email"]
    text: str = Field(..., min_length=1, max_length=300)
    count: int = Field(1, ge=1)
    examples: list[str] = Field(default_factory=list, max_length=5)
    email: Optional[EmailStr] = None


@router.post("/insights/requests/send")
async def send_request(
    body: SendRequest,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Send a feature request to the product team: the site's Slack channel,
    its signed webhook (event ``feature_request``), or an email address."""
    examples = [e[:300] for e in body.examples]
    console = get_settings().console_url.rstrip("/")
    link = f"{console}/websites/{site.id}/insights"
    if body.channel == "email":
        if not body.email:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give an email address")
        lines = [f"Visitors on {site.name} asked for this {body.count} time(s):", "", body.text, ""]
        lines += [f"- {e}" for e in examples] + ["", f"More in Insights: {link}"]
        html = templates.layout(
            "A feature request from your visitors",
            templates.paragraph(f"Visitors on {site.name} asked for this {body.count} time(s):")
            + templates.paragraph(body.text)
            + "".join(templates.paragraph(f"“{e}”") for e in examples)
            + templates.button("Open Insights", link))
        try:
            await email_out.enqueue(db, email_out.Email(
                to=str(body.email), subject=f"Feature request: {body.text[:80]}",
                text="\n".join(lines), html=html, kind="feature_request",
                tenant_id=site.tenant_id))
        except email_out.EmailNotConfigured as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
        await db.commit()
        return {"sent": True, "channel": "email"}

    cfg = await leads_store.get_integrations(db, site.site_key)
    payload = {"event": "feature_request", "site": site.name, "request": body.text,
               "count": body.count, "examples": examples, "insights_url": link}
    try:
        if body.channel == "slack":
            if not cfg["slack_webhook_url"]:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    "No Slack channel yet: add one under Leads → Integrations.")
            quoted = "\n".join(f"> {e}" for e in examples)
            msg = (f"*Feature request* from visitors on {site.name} (asked {body.count}×): "
                   f"{body.text}\n{quoted}\n<{link}|Open Insights>")
            await delivery._post(cfg["slack_webhook_url"], json.dumps({"text": msg}).encode(),
                                 {"Content-Type": "application/json"}, delivery_transport())
        else:
            if not cfg["webhook_url"]:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    "No webhook yet: add one under Leads → Integrations.")
            raw = json.dumps(payload, separators=(",", ":")).encode()
            await delivery._post(cfg["webhook_url"], raw, {
                "Content-Type": "application/json", "X-FluidBuddha-Event": "feature_request",
                "X-FluidBuddha-Signature": delivery.sign(cfg["webhook_secret"], raw)},
                delivery_transport())
    except (UnsafeURLError, RuntimeError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't deliver it: {exc}")
    return {"sent": True, "channel": body.channel}


def delivery_transport():
    """Tests swap in an httpx.MockTransport (as for lead delivery)."""
    return _transport


_transport = None
