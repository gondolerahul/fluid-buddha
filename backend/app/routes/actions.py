"""
Actions and custom components (M2-8).

Public (the widget, and Razorpay):

    POST /actions/confirm   {key, site?, session_id, run_id} → the run's outcome
    POST /actions/cancel    {key, site?, session_id, run_id}
    POST /actions/razorpay/{action_id}/webhook   payment_link.paid → run + lead "paid"

Console (actions need Admin: they hold payment keys):

    GET/POST       /tenant/websites/{id}/actions
    PUT/DELETE     /tenant/websites/{id}/actions/{aid}
    GET            /tenant/websites/{id}/actions/{aid}/secret   signing secret + Razorpay webhook URL
    GET            /tenant/websites/{id}/action-runs
    GET/POST       /tenant/websites/{id}/components
    PUT/DELETE     /tenant/websites/{id}/components/{cid}
    POST           /tenant/websites/{id}/components/preview     {spec, props} → what the widget draws
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.actions import run as runner
from app.actions import store
from app.actions.fields import ActionConfigError
from app.billing.razorpay import webhook_signature_ok
from app.config import get_settings
from app.db import get_session, session_scope
from app.orchestrator import custom_components as cc
from app.tenancy import store as tenancy
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.transport import guard

logger = logging.getLogger(__name__)

public = APIRouter(tags=["actions"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["actions"])

CONFIRM_RATE_PER_MIN = 30


def _uuid(v: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(v))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


# ---- public: the visitor confirms or cancels -----------------------------------

class RunRequest(BaseModel):
    key: Optional[str] = None
    site: Optional[str] = None
    session_id: str = Field(..., min_length=1, max_length=200)
    run_id: str = Field(..., min_length=1, max_length=64)


def visitor_view(run: dict[str, Any]) -> dict[str, Any]:
    """What the widget gets back: no inputs echoed beyond the summary."""
    res = run.get("result") or {}
    return {"id": run["id"], "status": run["status"], "message": res.get("message"),
            "url": res.get("url"), "error": run.get("error") if run["status"] == "failed" else None}


async def _resolve(db: AsyncSession, body: RunRequest, request: Request) -> str:
    try:
        resolved = await resolve_public_site(db, key=body.key, site=body.site, intelligence=None,
                                             origin=request.headers.get("origin"))
    except PublicAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
    if not guard._limiter.allow(f"actions:{resolved.site_key}", CONFIRM_RATE_PER_MIN):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
    return resolved.site_key


async def _tell_agent(site_key: str, session_id: str, label: str, run: dict[str, Any]) -> None:
    """The conversation learns the outcome: the voice socket through the live
    bus, a text conversation through the session store."""
    from app.live.bus import bus, session_topic
    from app.transport.session_store import store as sessions
    note = {"type": "action_outcome", "label": label, "status": run["status"],
            "message": (run.get("result") or {}).get("message") or run.get("error") or ""}
    try:
        await bus.publish(session_topic(site_key, session_id), note)
        state = await sessions.backend.get(session_id)
        if state is not None and state.site_key == site_key:
            state.add_turn(f"(I confirmed: {label})", f"({run['status']}: {note['message']})")
            await sessions.save(session_id, state)
    except Exception as exc:
        logger.debug("action outcome not passed on: %s", exc)


@public.post("/actions/confirm")
async def confirm(body: RunRequest, request: Request) -> dict:
    async with session_scope() as db:
        site_key = await _resolve(db, body, request)
        try:
            run = await runner.confirm(db, site_key, body.session_id, _uuid(body.run_id))
        except LookupError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such request")
        except PermissionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
        tid = (await db.execute(text("SELECT tenant_id FROM tenant_websites WHERE site_key = :s"),
                                {"s": site_key})).scalar()
        if tid is not None:
            await audit.record(db, action="action.run", tenant_id=tid, actor_email="visitor",
                               target_type="action_run", target_id=run["id"],
                               details={"action": run["action_name"], "status": run["status"],
                                        "amount": run["amount"]})
            await db.commit()
    await _tell_agent(site_key, body.session_id, run["action_name"], run)
    return visitor_view(run)


@public.post("/actions/cancel")
async def cancel(body: RunRequest, request: Request) -> dict:
    async with session_scope() as db:
        site_key = await _resolve(db, body, request)
        run = await store.get_run(db, site_key, _uuid(body.run_id), lock=True)
        if run is None or run["session_id"] != body.session_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such request")
        if run["status"] == "proposed":
            run = await store.finish(db, _uuid(body.run_id), status="cancelled", confirmed=False)
            await db.commit()
    await _tell_agent(site_key, body.session_id, run["action_name"], run)
    return visitor_view(run)


@public.post("/actions/razorpay/{action_id}/webhook")
async def razorpay_webhook(action_id: str, request: Request) -> Response:
    """Razorpay → the tenant's payment action: a paid link marks its run and lead."""
    raw = await request.body()
    async with session_scope() as db:
        row = (await db.execute(text(
            "SELECT id, kind FROM site_actions WHERE id = :id"), {"id": _uuid(action_id)})).first()
        if row is None or row[1] != "payment_link":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        secret = (await store.secrets_of(db, row[0])).get("webhook_secret", "")
        if not webhook_signature_ok(raw, request.headers.get("x-razorpay-signature"), secret):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad signature")
        try:
            event = json.loads(raw)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad body")
        if event.get("event") == "payment_link.paid":
            link = ((event.get("payload") or {}).get("payment_link") or {}).get("entity") or {}
            if link.get("id"):
                await store.mark_paid(db, str(link["id"]), link.get("amount_paid"))
                await db.commit()
    return Response(status_code=status.HTTP_200_OK)


async def check_payments(session_factory=session_scope) -> int:
    """Job: ask Razorpay about unpaid links (when its webhook isn't set up)."""
    paid = 0
    async with session_factory() as db:
        pending = await store.pending_payments(db)
        actions: dict[Any, Any] = {}
        for run in pending:
            aid = run["action_id"]
            if aid is None:
                continue
            if aid not in actions:
                a = await store.get_action(db, run["site_key"], aid)
                actions[aid] = (a, await store.secrets_of(db, aid)) if a else None
            if not actions[aid]:
                continue
            action, secret = actions[aid]
            try:
                link = await runner.razorpay_for(action, secret).fetch_payment_link(run["external_id"])
            except Exception as exc:
                logger.debug("payment link %s not checked: %s", run["external_id"], exc)
                continue
            if link.get("status") == "paid":
                await store.mark_paid(db, run["external_id"], link.get("amount_paid"))
                paid += 1
        await db.commit()
    return paid


# ---- console: actions ------------------------------------------------------------

class ActionIn(BaseModel):
    kind: Optional[str] = None
    name: str = Field(..., max_length=40)
    label: str = Field(..., max_length=80)
    description: str = Field("", max_length=400)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    # Typed only to change them; blank keeps the stored ones. Never read back.
    secrets: dict[str, str] = Field(default_factory=dict)


def _webhook_url(action_id: str) -> str:
    return f"{get_settings().public_api_url.rstrip('/')}/actions/razorpay/{action_id}/webhook"


def _console(a: store.Action) -> dict[str, Any]:
    out = a.public()
    if a.kind == "payment_link":
        out["razorpay_webhook_url"] = _webhook_url(str(a.id))
    return out


@admin.get("/actions")
async def list_actions(site: tenancy.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    return {"actions": [_console(a) for a in await store.list_actions(db, site.site_key)]}


@admin.post("/actions", status_code=status.HTTP_201_CREATED)
async def create_action(body: ActionIn, site: tenancy.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    try:
        a = await store.save_action(db, site.site_key, body.model_dump())
    except ActionConfigError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await db.commit()
    return _console(a)


@admin.put("/actions/{action_id}")
async def update_action(action_id: str, body: ActionIn,
                        site: tenancy.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    aid = _uuid(action_id)
    if await store.get_action(db, site.site_key, aid) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    try:
        a = await store.save_action(db, site.site_key, body.model_dump(), aid)
    except ActionConfigError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await db.commit()
    return _console(a)


@admin.delete("/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(action_id: str, site: tenancy.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> Response:
    if not await store.delete_action(db, site.site_key, _uuid(action_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin.get("/actions/{action_id}/secret")
async def action_secret(action_id: str, site: tenancy.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    """The signing secret the tenant's endpoint verifies requests with."""
    a = await store.get_action(db, site.site_key, _uuid(action_id))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
    sec = await store.secrets_of(db, a.id)
    return {"signing_secret": sec.get("signing_secret"),
            "razorpay_webhook_url": _webhook_url(str(a.id)) if a.kind == "payment_link" else None,
            "has_razorpay_webhook_secret": bool(sec.get("webhook_secret"))}


@admin.get("/action-runs")
async def list_runs(site: tenancy.Website = Depends(owned_website),
                    db: AsyncSession = Depends(get_session)) -> dict:
    return {"runs": await store.list_runs(db, site.site_key, limit=100)}


@admin.get("/action-runs/{run_id}/quote.pdf")
async def quote_pdf(run_id: str, site: tenancy.Website = Depends(owned_website),
                    db: AsyncSession = Depends(get_session)) -> Response:
    """A confirmed quote request as a one-page PDF (M2-8 follow-up)."""
    from app.actions.pdf import quote_pdf as render
    from app.orchestrator.profile import ensure_profile

    run = await store.get_run(db, site.site_key, _uuid(run_id))
    if run is None or run["kind"] != "quote_request" or run["status"] != "done":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such quote request")
    profile = await ensure_profile(site.site_key)
    action = next((a for a in await store.list_actions(db, site.site_key)
                   if a.name == run["action_name"]), None)
    pdf = render(company=profile.company_name, action_label=action.label if action else run["action_name"],
                 run=run)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="quote-{str(run["id"])[:8]}.pdf"'})


# ---- console: components -----------------------------------------------------------

class ComponentIn(BaseModel):
    name: str = Field(..., max_length=40)
    label: str = Field(..., max_length=80)
    description: str = Field("", max_length=400)
    kind: str
    props_schema: dict[str, Any]
    template: Optional[dict[str, Any]] = None
    iframe_url: Optional[str] = Field(None, max_length=500)
    enabled: bool = True


class PreviewIn(BaseModel):
    spec: ComponentIn
    props: dict[str, Any] = Field(default_factory=dict)


@admin.get("/components")
async def list_components(site: tenancy.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> dict:
    return {"components": [c.public() for c in await cc.list_components(db, site.site_key)]}


@admin.post("/components", status_code=status.HTTP_201_CREATED)
async def create_component(body: ComponentIn, site: tenancy.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> dict:
    try:
        c = await cc.save_component(db, site.site_key, body.model_dump())
    except cc.ComponentSpecError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await db.commit()
    return c.public()


@admin.put("/components/{component_id}")
async def update_component(component_id: str, body: ComponentIn,
                           site: tenancy.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> dict:
    try:
        c = await cc.save_component(db, site.site_key, body.model_dump(), _uuid(component_id))
    except cc.ComponentSpecError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Component not found")
    await db.commit()
    return c.public()


@admin.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(component_id: str, site: tenancy.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> Response:
    if not await cc.delete_component(db, site.site_key, _uuid(component_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Component not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin.post("/components/preview")
async def preview_component(body: PreviewIn,
                            site: tenancy.Website = Depends(owned_website)) -> dict:
    """What the widget would draw for these props (checks the spec too)."""
    try:
        spec = cc.clean_spec(body.spec.model_dump())
        comp = cc.CustomComponent(id=uuid.uuid4(), site_key=site.site_key, **spec)
        ctype, state = cc.render(comp, body.props)
    except (cc.ComponentSpecError, cc.PropsError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if ctype != "embed":
        from app.orchestrator.components import normalize_component
        ctype, state = normalize_component(ctype, state)
    return {"component_type": ctype, "initial_state": state}


async def ensure_extras(site_key: str) -> None:
    """Load a site's actions and components for the agent (cached ~30 s)."""
    try:
        async with session_scope() as db:
            await store.ensure_actions(db, site_key)
            await cc.ensure_components(db, site_key)
    except Exception as exc:   # the agent still answers without them
        logger.warning("actions/components for %s not loaded: %s", site_key, exc)


async def proposal_cards(site_key: str, session_id: str, proposals: list) -> list[dict[str, Any]]:
    """Store the agent's proposals as runs; the widget's confirmation cards.
    A proposal over the conversation's limit is dropped (best-effort)."""
    cards = []
    for action, inputs in proposals or []:
        try:
            async with session_scope() as db:
                run = await store.propose(db, action, session_id, inputs)
                await db.commit()
        except Exception as exc:
            logger.info("proposal %s not stored: %s", action.name, exc)
            continue
        cards.append({"id": run["id"], "kind": action.kind, "label": action.label,
                      "summary": run["summary"]})
    return cards
