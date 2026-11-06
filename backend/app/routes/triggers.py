"""
Proactive triggers (M2-3).

Public (the widget, from the customer's site; key and domain checked like
every public call, bots ignored):

    GET  /widget/triggers?key=…          the site's enabled rules
    GET  /widget/triggers/message?key=…&rule_id=…&page=…&title=…&lang=…
                                         the agent's opener for this page (rules
                                         with "let the agent write it"; cached)
    POST /widget/triggers/event          {key, visitor, rule_id, event, page?}
                                         event: shown | clicked | dismissed | engaged
                                         (JSON sent as text/plain is fine: sendBeacon)

Console (reads Viewer, changes Editor; every change audit-logged):

    GET    /tenant/websites/{id}/triggers          rules + last 30 days' numbers
    POST   /tenant/websites/{id}/triggers
    PUT    /tenant/websites/{id}/triggers/{rule}
    DELETE /tenant/websites/{id}/triggers/{rule}
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, session_scope
from app.experiments.bots import is_bot
from app.routes.experiments import _body, _site_key, _visitor
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.triggers import store as triggers
from app.triggers.store import EVENTS, RuleIn

public = APIRouter(prefix="/widget/triggers", tags=["triggers"])
admin = APIRouter(prefix="/tenant/websites/{website_id}/triggers", tags=["triggers"])


@public.get("")
async def site_triggers(request: Request,
                        key: str = Query(..., min_length=1, max_length=200)) -> dict:
    try:
        async with session_scope() as db:
            resolved = await resolve_public_site(db, key=key, site=None, intelligence=None,
                                                 origin=request.headers.get("origin"))
            rules = await triggers.rules(db, resolved.site_key, enabled_only=True) \
                if resolved.website is not None else []
    except PublicAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
    return {"rules": [triggers.public(r) for r in rules]}


@public.get("/message")
async def trigger_message(request: Request,
                          key: str = Query(..., min_length=1, max_length=200),
                          rule_id: uuid.UUID = Query(...),
                          page: str = Query("/", max_length=500),
                          title: str = Query("", max_length=300),
                          lang: str = Query("en", max_length=5)) -> dict:
    from app.config import get_settings
    from app.orchestrator.profile import load_profile
    from app.triggers.compose import message_for

    settings = get_settings()
    try:
        async with session_scope() as db:
            resolved = await resolve_public_site(db, key=key, site=None, intelligence=None,
                                                 origin=request.headers.get("origin"))
            rule = next((r for r in await triggers.rules(db, resolved.site_key, enabled_only=True)
                         if r["id"] == str(rule_id)), None) if resolved.website is not None else None
            if rule is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "No such trigger")
            if is_bot(request.headers.get("user-agent"), None):
                return {"message": rule["message"]}
            rt = getattr(request.app.state, "runtime", None)
            from app.ai.providers import config_for_site, current_site
            current_site.set(resolved.site_key)
            byo = await config_for_site(resolved.site_key)
            llm = None if rt is None or (settings.mock_ai and byo is None) else rt.engines.llm
            profile = await load_profile(db, resolved.site_key)
            message = await message_for(db, site_key=resolved.site_key, rule=rule, page=page,
                                        title=title, lang=lang, llm=llm, model=settings.fast_model,
                                        company=profile.company_name)
    except PublicAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
    return {"message": message}


@public.post("/event", status_code=status.HTTP_202_ACCEPTED)
async def trigger_event(request: Request) -> dict:
    data = await _body(request)
    visitor = _visitor(data)
    event = str(data.get("event") or "")
    if event not in EVENTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown event")
    try:
        rule_id = uuid.UUID(str(data.get("rule_id")))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid rule id")
    if is_bot(request.headers.get("user-agent"), data.get("automated")):
        return {"counted": False}
    async with session_scope() as db:
        site_key = await _site_key(db, data, request)
        counted = bool(site_key) and await triggers.record(
            db, site_key, rule_id, visitor, event, str(data.get("page") or "") or None)
    return {"counted": counted}


@admin.get("")
async def list_triggers(site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    stats = await triggers.stats(db, site.site_key)
    return {"rules": [{**r, "stats": stats.get(r["id"])}
                      for r in await triggers.rules(db, site.site_key)]}


@admin.post("", status_code=status.HTTP_201_CREATED)
async def create_trigger(body: RuleIn, site: store.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> dict:
    try:
        rule = await triggers.create(db, site.site_key, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    await db.commit()
    return rule


@admin.put("/{rule_id}")
async def update_trigger(rule_id: uuid.UUID, body: RuleIn,
                         site: store.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> dict:
    rule = await triggers.update(db, site.site_key, rule_id, body)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trigger not found")
    await db.commit()
    return rule


@admin.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(rule_id: uuid.UUID, site: store.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> None:
    if not await triggers.delete(db, site.site_key, rule_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trigger not found")
    await db.commit()
