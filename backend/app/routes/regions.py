"""
Adaptive regions, G1 (Phase 1 of the generative experience plan).

Public (the widget's ``<fb-region>`` elements; key + origin checked):

    POST /experience/regions   {key, site?, visitor?, page, regions[], signals{}, lang?, persona?, automated?}
                               → {regions: {name: section}, plan_id, intent, cache, tokens,
                                  bundle?, pending, retry_after_ms?, arm?}

Console (per website):

    GET/PUT  /tenant/websites/{id}/regions/settings          {regions_enabled}
    GET      /tenant/websites/{id}/regions                   slots
    PUT      /tenant/websites/{id}/regions/{name}            create / update a slot
    DELETE   /tenant/websites/{id}/regions/{name}
    GET      /tenant/websites/{id}/intent-families
    PUT      /tenant/websites/{id}/intent-families/{slug}
    DELETE   /tenant/websites/{id}/intent-families/{slug}
    GET      /tenant/websites/{id}/intent-families/suggest   proposals from the site's routes
    POST     /tenant/websites/{id}/intent/resolve            try signals → intent
    GET      /tenant/websites/{id}/plans                     ?family=&persona=&page=&status=
    POST     /tenant/websites/{id}/plans/generate            {page, family?, signals?, persona?, lang?}
    GET      /tenant/websites/{id}/plans/{pid}               plan + bound regions + HTML preview
    PUT      /tenant/websites/{id}/plans/{pid}               {status: auto|pinned|blocked}
    DELETE   /tenant/websites/{id}/plans/{pid}
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, session_scope
from app.experience import regions_store as rs
from app.experience.intent import GENERAL, Intent, Signals, suggest_families
from app.experience.manifest import ensure_manifest, load_manifest
from app.experience.regions import build_and_store, intent_for, render_plan, serve_regions
from app.experiments import store as exp_store
from app.experiments.bots import is_bot
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import PublicAccessError, resolve_public_site

public = APIRouter(prefix="/experience", tags=["regions"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["regions"])

_MAX_BODY = 8192
PUBLIC_PER_MIN = 240
_EMPTY: dict[str, Any] = {"regions": {}, "pending": False}


# ---- public -----------------------------------------------------------------

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


async def _arm_allows_regions(db: AsyncSession, site_key: str, visitor: Optional[str],
                              bot: bool) -> tuple[bool, dict[str, Any]]:
    """Whether this visitor's experiment arm gets generated regions."""
    exp = await exp_store.current(db, site_key)
    if exp is None or not exp.running:
        return True, {}
    if not visitor:
        # Unidentified visitors can't be measured: keep a region test clean.
        return exp.subject != "regions", {}
    got = await exp_store.enroll(db, site_key, visitor, bot=bot)
    if got is None:
        return exp.subject != "regions", {}
    info = {"experiment_id": got["experiment_id"], "arm": got["arm"]}
    if got["arm"] == "holdout":
        return False, info  # FluidBuddha is off for the holdout
    if exp.subject == "regions":
        return got["overrides"].get("regions") is not False, info
    return True, info


@public.post("/regions")
async def regions_for_page(request: Request) -> dict:
    from app.transport import guard

    data = await _body(request)
    names = [str(n) for n in (data.get("regions") or []) if isinstance(n, str)][:12]
    async with session_scope() as db:
        try:
            resolved = await resolve_public_site(db, key=data.get("key"), site=data.get("site"),
                                                 intelligence=None, origin=request.headers.get("origin"))
        except PublicAccessError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
        if resolved.website is None or not names:
            return {**_EMPTY, "reason": "not_available"}
        site_key = resolved.site_key
        if not guard._limiter.allow(f"regions:{site_key}", PUBLIC_PER_MIN):
            return {**_EMPTY, "reason": "rate_limited"}
        if not await rs.regions_enabled(db, site_key):
            return {**_EMPTY, "reason": "off"}
        bot = is_bot(request.headers.get("user-agent"), data.get("automated"))
        if bot:
            return {**_EMPTY, "reason": "bot"}  # crawlers see the host's own content
        visitor = str(data.get("visitor") or "")
        visitor = visitor if exp_store.VISITOR_RE.match(visitor) else None
        allowed, arm = await _arm_allows_regions(db, site_key, visitor, bot)
        if not allowed:
            return {**_EMPTY, "reason": "experiment_arm", **arm}
        sig = Signals.from_dict(data.get("signals") if isinstance(data.get("signals"), dict) else {},
                                page=str(data.get("page") or "/"),
                                lang="hi" if data.get("lang") == "hi" else "en",
                                persona=str(data.get("persona") or "")[:40])
        out = await serve_regions(db, request.app.state.runtime, site_key, names=names, sig=sig)
        return {**out, **arm}


# ---- console: settings and slots ----------------------------------------------

class SettingsIn(BaseModel):
    regions_enabled: bool


@admin.get("/regions/settings")
async def get_settings_(site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    return {"regions_enabled": await rs.regions_enabled(db, site.site_key)}


@admin.put("/regions/settings")
async def put_settings(body: SettingsIn, site: store.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    await rs.set_regions_enabled(db, site.site_key, body.regions_enabled)
    return {"regions_enabled": body.regions_enabled}


def _globs(v: list[str]) -> list[str]:
    out = []
    for g in v[:20]:
        g = str(g).strip().lower()
        if not g:
            continue
        if not g.startswith("/") or len(g) > 200 or any(c in g for c in " <>\"'"):
            raise ValueError("page patterns look like /pricing or /blog/*")
        out.append(g)
    return out


class SlotIn(BaseModel):
    label: str = Field("", max_length=80)
    purpose: str = Field("", max_length=300)
    components: list[str] = Field(default_factory=list, max_length=20)
    pages: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True

    @field_validator("pages")
    @classmethod
    def _pages(cls, v: list[str]) -> list[str]:
        return _globs(v)


@admin.get("/regions")
async def list_regions(site: store.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    await ensure_manifest(site.site_key)
    manifest = load_manifest(site.site_key)
    return {
        "regions": [s.to_dict() for s in await rs.list_slots(db, site.site_key)],
        "components": [{"id": e.id, "renderer": e.renderer, "purpose": e.purpose} for e in manifest.entries()],
    }


@admin.put("/regions/{name}")
async def put_region(name: str, body: SlotIn, site: store.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    if not rs.SLUG_RE.match(name):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A region name is lowercase letters, digits and dashes, starting with a letter.")
    await ensure_manifest(site.site_key)
    manifest = load_manifest(site.site_key)
    unknown = [c for c in body.components if manifest.get(c) is None]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Not in the approved components: {', '.join(unknown)}")
    slot = await rs.upsert_slot(db, site.site_key, {"name": name, **body.model_dump()})
    return slot.to_dict()


@admin.delete("/regions/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_region(name: str, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> None:
    if not await rs.delete_slot(db, site.site_key, name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Region not found")


# ---- console: intent families --------------------------------------------------

class FamilyIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=400)
    stage: str = Field("", max_length=20)
    rules: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(0, ge=-100, le=100)
    enabled: bool = True


@admin.get("/intent-families")
async def list_intent_families(site: store.Website = Depends(owned_website),
                               db: AsyncSession = Depends(get_session)) -> dict:
    return {"families": [f.to_dict() for f in await rs.list_families(db, site.site_key)]}


@admin.get("/intent-families/suggest")
async def suggest_intent_families(site: store.Website = Depends(owned_website),
                                  db: AsyncSession = Depends(get_session)) -> dict:
    from app.orchestrator.profile import ensure_profile

    profile = await ensure_profile(site.site_key)
    routes = [str(r.get("path") if isinstance(r, dict) else r) for r in (getattr(profile, "routes", None) or [])]
    personas = [(p.slug, p.label) for p in (getattr(profile, "personas", None) or [])
                if getattr(p, "slug", None)]
    have = {f.slug for f in await rs.list_families(db, site.site_key)}
    return {"suggestions": [s for s in suggest_families(routes, personas) if s["slug"] not in have]}


@admin.put("/intent-families/{slug}")
async def put_intent_family(slug: str, body: FamilyIn, site: store.Website = Depends(owned_website),
                            db: AsyncSession = Depends(get_session)) -> dict:
    if not rs.SLUG_RE.match(slug):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A family slug is lowercase letters, digits and dashes, starting with a letter.")
    fam = await rs.upsert_family(db, site.site_key, {
        "slug": slug, "label": body.label.strip(), "description": body.description.strip(),
        "stage": body.stage.strip().lower(), "rules": rs.clean_rules(body.rules),
        "priority": body.priority, "enabled": body.enabled})
    return fam.to_dict()


@admin.delete("/intent-families/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_intent_family(slug: str, site: store.Website = Depends(owned_website),
                               db: AsyncSession = Depends(get_session)) -> None:
    if not await rs.delete_family(db, site.site_key, slug):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Intent family not found")


class ResolveIn(BaseModel):
    page: str = Field("/", max_length=300)
    signals: dict[str, Any] = Field(default_factory=dict)


@admin.post("/intent/resolve")
async def try_resolve(body: ResolveIn, request: Request, site: store.Website = Depends(owned_website),
                      db: AsyncSession = Depends(get_session)) -> dict:
    sig = Signals.from_dict(body.signals, page=body.page)
    intent = await intent_for(db, request.app.state.runtime, site.site_key, sig, background_model=False)
    return {"intent": intent.to_dict(), "signal_text": sig.text()}


# ---- console: plans --------------------------------------------------------------

@admin.get("/plans")
async def list_plans(family: Optional[str] = None, persona: Optional[str] = None, page: Optional[str] = None,
                     status_filter: Optional[str] = None, site: store.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    rows = await rs.list_plans(db, site.site_key, family=family, persona=persona, page=page,
                               status=status_filter)
    for r in rows:
        r.pop("plan", None)
    return {"plans": rows}


async def _plan_view(site_key: str, row: dict[str, Any]) -> dict[str, Any]:
    from app.design.system import ensure_design, load_design_system
    from app.experience.preview import render_preview
    from app.orchestrator.profile import profile_for

    await ensure_manifest(site_key)
    await ensure_design(site_key)
    ctx = {"site_key": site_key, "currency": profile_for(site_key).currency, "lang": row["lang"],
           "persona": row["persona"], "page": row["page"]}
    regions, _ = await render_plan(site_key, row["plan"], ctx)
    return {**row, "rendered": regions,
            "preview_html": render_preview(regions, load_design_system(site_key), title=row["family"])}


class GenerateIn(BaseModel):
    page: str = Field("/", max_length=300)
    family: Optional[str] = Field(None, max_length=40)
    signals: dict[str, Any] = Field(default_factory=dict)
    persona: str = Field("", max_length=40)
    lang: str = Field("en", pattern="^(en|hi)$")


@admin.post("/plans/generate", status_code=status.HTTP_201_CREATED)
async def generate_plan(body: GenerateIn, request: Request, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    from app.experience.regions import _content_version

    rt = request.app.state.runtime
    sig = Signals.from_dict(body.signals, page=body.page, lang=body.lang, persona=body.persona)
    slots = [s for s in await rs.list_slots(db, site.site_key) if s.enabled and s.on_page(sig.page)]
    if not slots:
        raise HTTPException(status.HTTP_409_CONFLICT, "No enabled regions match that page yet.")
    families = await rs.list_families(db, site.site_key)
    if body.family and body.family != GENERAL:
        fam = next((f for f in families if f.slug == body.family), None)
        if fam is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Intent family not found")
        intent = Intent(fam.slug, fam.label, fam.stage, 1.0, "console")
    elif body.family == GENERAL:
        intent = Intent(source="console")
    else:
        intent = await intent_for(db, rt, site.site_key, sig, background_model=False)
    await ensure_manifest(site.site_key)
    manifest = load_manifest(site.site_key)
    content = await _content_version(db, site.site_key)
    key = rs.plan_cache_key(family=intent.family, persona=sig.persona, lang=sig.lang, page=sig.page,
                            regions=[s.name for s in slots], content_version=content,
                            manifest_version=manifest.version)
    row = await build_and_store(db, rt, site.site_key, slots, intent, sig, key=key, content=content)
    view = await _plan_view(site.site_key, row)
    view["intent"] = intent.to_dict()
    return view


@admin.get("/plans/{pid}")
async def get_plan(pid: str, site: store.Website = Depends(owned_website),
                   db: AsyncSession = Depends(get_session)) -> dict:
    row = await rs.get_plan(db, site.site_key, pid)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    return await _plan_view(site.site_key, row)


class PlanStatusIn(BaseModel):
    status: str = Field(..., pattern="^(auto|pinned|blocked)$")


@admin.put("/plans/{pid}")
async def set_plan_status(pid: str, body: PlanStatusIn, site: store.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> dict:
    row = await rs.set_plan_status(db, site.site_key, pid, body.status)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    row.pop("plan", None)
    return row


@admin.delete("/plans/{pid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(pid: str, site: store.Website = Depends(owned_website),
                      db: AsyncSession = Depends(get_session)) -> None:
    if not await rs.delete_plan(db, site.site_key, pid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
