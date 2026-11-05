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
    GET  /tenant/websites/{id}/experiment/plan     ?baseline=&mde=&holdout_pct=
                                                   visitors needed and days left

Variant tests (M2-4), one experiment per site at a time:

    GET  /tenant/websites/{id}/tests               past and current tests
    POST /tenant/websites/{id}/tests               {name, subject, variants, holdout_pct, goal_path}
    GET  /tenant/websites/{id}/tests/plan          ?variants=&baseline=&mde=&holdout_pct=
    GET  /tenant/websites/{id}/tests/{tid}         each variant vs the control, verdict
    POST /tenant/websites/{id}/tests/{tid}/stop
    POST /tenant/websites/{id}/tests/{tid}/promote {variant}: make it the site's
                                                   default and end the test

The enrolment answer carries the visitor's variant ``overrides`` (applied by
the widget) and the site's ``defaults`` (greeting, design level).

Enrolment turns bots away (their User-Agent, or ``automated`` — the widget's
``navigator.webdriver``); see ``app/experiments/bots.py``.
"""
from __future__ import annotations

import json
import math
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text

from app.db import get_session, session_scope
from app.experiments import store as exp_store
from app.experiments.bots import is_bot
from app.orchestrator.profile import ensure_profile, load_profile, save_profile
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, ResolvedSite, resolve_public_site
from app.triggers import store as trigger_store

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


async def _resolve(db: AsyncSession, data: dict, request: Request) -> ResolvedSite:
    try:
        return await resolve_public_site(
            db, key=data.get("key"), site=data.get("site"), intelligence=None,
            origin=request.headers.get("origin"),
        )
    except PublicAccessError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)


async def _site_key(db: AsyncSession, data: dict, request: Request) -> Optional[str]:
    """The tenant site the key resolves to; None for built-in demo sites, which
    never run experiments."""
    resolved = await _resolve(db, data, request)
    return resolved.site_key if resolved.website is not None else None


_NO_ARM = {"experiment_id": None, "arm": None, "goal_path": None, "overrides": {}}


@public.post("/enroll")
async def enroll(request: Request) -> dict:
    data = await _body(request)
    visitor = _visitor(data)
    async with session_scope() as db:
        resolved = await _resolve(db, data, request)
        if resolved.website is None:
            return {**_NO_ARM, "defaults": {}}
        bot = is_bot(request.headers.get("user-agent"), data.get("automated"))
        result = await exp_store.enroll(db, resolved.site_key, visitor, bot=bot)
    profile = await ensure_profile(resolved.site_key)
    defaults = {"greeting": profile.greeting or None, "design": resolved.website.design,
                # Languages (M2-7): the widget picks its labels from these.
                "languages": profile.languages, "widget_language": profile.widget_language,
                "greeting_hi": profile.greeting_hi or None}
    return {**(result or _NO_ARM), "defaults": defaults}


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
                "goal_path": None, "status": None, "started_at": None, "ended_at": None,
                "bots_ignored": 0}
    return exp.public()


@admin.get("/experiment")
async def get_experiment(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return _settings(await exp_store.current(db, site.site_key, kind="holdout"))


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
    try:
        exp, started = await exp_store.configure(
            db, site.site_key, enabled=body.enabled, holdout_pct=body.holdout_pct, goal_path=goal)
    except exp_store.Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return {**_settings(exp), "started_new_run": started}


@admin.post("/experiment/restart")
async def restart_experiment(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        exp = await exp_store.restart(db, site.site_key)
    except exp_store.Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if exp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No experiment to restart")
    return _settings(exp)


@admin.get("/experiment/results")
async def experiment_results(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> Optional[dict]:
    exp = await exp_store.current(db, site.site_key, kind="holdout")
    if exp is None:
        return None
    return await exp_store.results(db, exp)


@admin.get("/experiment/plan")
async def experiment_plan(
    baseline: Optional[float] = Query(None, gt=0, lt=1),
    mde: float = Query(exp_store.DEFAULT_MDE, gt=0, le=10),
    holdout_pct: Optional[int] = Query(None, ge=1, le=50),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    exp = await exp_store.current(db, site.site_key, kind="holdout")
    return await exp_store.plan(db, exp, baseline=baseline, mde=mde, holdout_pct=holdout_pct)


# ---- variant tests (M2-4) --------------------------------------------------------

class VariantIn(BaseModel):
    label: str = Field("", max_length=60)
    overrides: dict[str, Any] = Field(default_factory=dict)


class TestIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    subject: str
    variants: list[VariantIn] = Field(..., min_length=2, max_length=len(exp_store.VARIANT_KEYS))
    holdout_pct: int = Field(0, ge=0, le=50)
    goal_path: Optional[str] = Field(None, max_length=300)


class PromoteIn(BaseModel):
    variant: str = Field(..., pattern="^[a-d]$")


async def _site_options(db: AsyncSession, site_key: str) -> dict:
    profile = await load_profile(db, site_key)
    rules = await trigger_store.rules(db, site_key)
    return {"personas": profile.persona_slugs, "rule_ids": [r["id"] for r in rules]}


async def _test(db: AsyncSession, site: store.Website, test_id: uuid.UUID) -> exp_store.Experiment:
    exp = await exp_store.get(db, site.site_key, test_id)
    if exp is None or not exp.is_test:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such test")
    return exp


@admin.get("/tests")
async def list_tests(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    running = await exp_store.current(db, site.site_key)
    return {"tests": await exp_store.list_tests(db, site.site_key),
            "holdout_running": bool(running and running.running and not running.is_test)}


@admin.post("/tests", status_code=status.HTTP_201_CREATED)
async def start_test(
    body: TestIn,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        goal = exp_store.clean_goal_path(body.goal_path)
        variants = exp_store.clean_variants(
            body.subject, [v.model_dump() for v in body.variants],
            **await _site_options(db, site.site_key))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    exp = await exp_store.start_test(
        db, site.site_key, name=body.name.strip(), subject=body.subject, variants=variants,
        holdout_pct=body.holdout_pct, goal_path=goal)
    return exp.public()


@admin.get("/tests/plan")
async def plan_test(
    variants: int = Query(3, ge=2, le=len(exp_store.VARIANT_KEYS)),
    baseline: float = Query(exp_store.DEFAULT_BASELINE, gt=0, lt=1),
    mde: float = Query(exp_store.DEFAULT_MDE, gt=0, le=10),
    holdout_pct: int = Query(0, ge=0, le=50),
    site: store.Website = Depends(owned_website),
) -> dict:
    """Before a test starts: visitors it needs for a given lift."""
    from app.experiments.stats import sample_size_arms
    return {"baseline": baseline, "mde": mde, "variants": variants, "holdout_pct": holdout_pct,
            "needed": sample_size_arms(baseline, mde, variants, holdout_pct / 100)}


@admin.get("/tests/{test_id}")
async def test_detail(
    test_id: uuid.UUID,
    mde: float = Query(exp_store.DEFAULT_MDE, gt=0, le=10),
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await exp_store.variant_results(db, await _test(db, site, test_id), mde=mde)


@admin.post("/tests/{test_id}/stop")
async def stop_test(
    test_id: uuid.UUID,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return (await exp_store.stop_test(db, await _test(db, site, test_id))).public()


@admin.post("/tests/{test_id}/promote")
async def promote_variant(
    test_id: uuid.UUID,
    body: PromoteIn,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Make a variant the site's default: the greeting, starting persona and
    tour switch go to the agent profile, the design level to the website, and
    for a trigger test the winning variant's triggers are switched on and the
    other tested ones off. Then the test ends."""
    exp = await _test(db, site, test_id)
    v = exp.variant(body.variant)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such variant")
    o = v["overrides"]
    if exp.subject in ("greeting", "persona", "tour"):
        profile = await load_profile(db, site.site_key)
        if exp.subject == "greeting":
            profile.greeting = o["greeting"]
        elif exp.subject == "persona":
            if o["persona"] and o["persona"] not in profile.persona_slugs:
                raise HTTPException(status.HTTP_409_CONFLICT, "That persona no longer exists")
            profile.default_persona = o["persona"]
        else:
            profile.tour_enabled = o["tour"]
        await save_profile(db, profile)
    elif exp.subject == "design":
        await store.update_website(db, site.id, site.tenant_id, design=o["design"])
    elif exp.subject == "trigger":
        tested = sorted({i for x in exp.variants for i in x["overrides"]["triggers"]})
        if tested:
            await db.execute(
                text("UPDATE trigger_rules SET enabled = (CAST(id AS text) = ANY(:on)), "
                     "updated_at = now() WHERE site_key = :s AND CAST(id AS text) = ANY(:all)"),
                {"on": o["triggers"], "all": tested, "s": site.site_key})
            await db.commit()
    return (await exp_store.mark_promoted(db, exp, body.variant)).public()
