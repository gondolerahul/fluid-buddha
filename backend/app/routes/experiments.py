"""
Holdout A/B API (WS11).

Public (called by the widget from the customer's site; the widget key and the
site's domain are checked like every public call):

    POST /experiment/enroll   {key, site?, visitor}                → {experiment_id, arm, goal_path}
    POST /experiment/convert  {key, site?, visitor, experiment_id, name, value?}

Both read the body as JSON whatever its content type, so the widget can send
a conversion with ``navigator.sendBeacon`` (text/plain, no CORS preflight) as
the page unloads.

Tenant (console):

    GET  /tenant/websites/{id}/experiment          settings of the latest run
    PUT  /tenant/websites/{id}/experiment          {enabled, holdout_pct, goal_path}
    POST /tenant/websites/{id}/experiment/restart  a fresh run, same settings
    GET  /tenant/websites/{id}/experiment/results  lift vs holdout with CIs
"""
from __future__ import annotations

import json
import math
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, session_scope
from app.experiments import store as exp_store
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site

public = APIRouter(prefix="/experiment", tags=["experiments"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["experiments"])

_MAX_BODY = 4096


async def _body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Body too large")
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be JSON")
    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Body must be a JSON object")
    return data


def _visitor(data: dict) -> str:
    v = str(data.get("visitor") or "")
    if not exp_store.VISITOR_RE.match(v):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid visitor id")
    return v


async def _site_key(db: AsyncSession, data: dict, request: Request) -> Optional[str]:
    """The tenant site the key resolves to; None for built-in demo sites, which
    never run experiments."""
    try:
        resolved = await resolve_public_site(
            db, key=data.get("key"), site=data.get("site"), intelligence=None,
            origin=request.headers.get("origin"),
        )
    except PublicAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
    return resolved.site_key if resolved.website is not None else None


@public.post("/enroll")
async def enroll(request: Request) -> dict:
    data = await _body(request)
    visitor = _visitor(data)
    async with session_scope() as db:
        site_key = await _site_key(db, data, request)
        result = await exp_store.enroll(db, site_key, visitor) if site_key else None
    return result or {"experiment_id": None, "arm": None, "goal_path": None}


@public.post("/convert", status_code=status.HTTP_202_ACCEPTED)
async def convert(request: Request) -> dict:
    data = await _body(request)
    visitor = _visitor(data)
    try:
        experiment_id = uuid.UUID(str(data.get("experiment_id")))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid experiment id")
    name = str(data.get("name") or "goal")
    if not exp_store.GOAL_NAME_RE.match(name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid goal name")
    value = data.get("value")
    if value is not None:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = None
        if value is not None and not math.isfinite(value):
            value = None
    async with session_scope() as db:
        site_key = await _site_key(db, data, request)
        counted = bool(site_key) and await exp_store.record_conversion(
            db, site_key, experiment_id, visitor, name, value)
    return {"counted": counted}


# ---- console ----------------------------------------------------------------------

class ExperimentUpdate(BaseModel):
    enabled: bool
    holdout_pct: int = Field(exp_store.DEFAULT_HOLDOUT_PCT, ge=1, le=50)
    goal_path: Optional[str] = Field(None, max_length=300)


def _settings(exp: Optional[exp_store.Experiment]) -> dict:
    if exp is None:
        return {"id": None, "enabled": False, "holdout_pct": exp_store.DEFAULT_HOLDOUT_PCT,
                "goal_path": None, "status": None, "started_at": None, "ended_at": None}
    return exp.public()


@admin.get("/experiment")
async def get_experiment(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return _settings(await exp_store.current(db, site.site_key))


@admin.put("/experiment")
async def put_experiment(
    body: ExperimentUpdate,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        goal = exp_store.clean_goal_path(body.goal_path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    exp, started = await exp_store.configure(
        db, site.site_key, enabled=body.enabled, holdout_pct=body.holdout_pct, goal_path=goal)
    return {**_settings(exp), "started_new_run": started}


@admin.post("/experiment/restart")
async def restart_experiment(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    exp = await exp_store.restart(db, site.site_key)
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No experiment to restart")
    return _settings(exp)


@admin.get("/experiment/results")
async def experiment_results(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> Optional[dict]:
    exp = await exp_store.current(db, site.site_key)
    if exp is None:
        return None
    return await exp_store.results(db, exp)
