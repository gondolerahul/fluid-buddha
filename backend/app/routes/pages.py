"""
Composed pages, G2 (Phase 2 of the generative experience plan).

Public:

    GET  /experience/page?key=&path=&fbv=&utm_*=&q=&referrer=&lang=&persona=
         → {status, html, css, head, data, plan_id, route, intent, tokens, bundle?, pending}
         Called server-side by the Next.js adapter (no Origin header) or by a
         browser on the site's own domain.
    POST /experience/lead       the no-JavaScript enquiry form (form-encoded), → 303 back
    GET  /g/{site_key}/{path}   the same page as a full HTML document (preview / non-Next sites)

Console (per website):

    GET/POST /tenant/websites/{id}/routes          · PUT/DELETE …/routes/{rid}
    PUT      /tenant/websites/{id}/routes/{rid}/canonical   {plan: plan_cache id | null}
    POST     /tenant/websites/{id}/routes/{rid}/generate    {family?, path?} → page plan + preview
    GET      /tenant/websites/{id}/entities                 types and counts
    GET      /tenant/websites/{id}/entities/{type}          records
    PUT      /tenant/websites/{id}/entities/{type}/{key}    · DELETE
    POST     /tenant/websites/{id}/entities/import          {type, format, key_field, content}
    GET/POST /tenant/websites/{id}/connectors · DELETE …/{cid} · POST …/{cid}/sync
"""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session, session_scope
from app.experience import entities as ents
from app.experience import regions_store as rs
from app.experience import routes_store as routes
from app.experience.intent import GENERAL, Intent, Signals
from app.experience.manifest import ensure_manifest, load_manifest
from app.experience.pages import bind_page, build_and_store_page, serve_page
from app.experience.regions import _content_version, intent_for
from app.experiments.bots import is_bot
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.public_access import _origin_allowed
from app.tenancy.url_fetch import UnsafeURLError, check_url, fetch_public

public = APIRouter(tags=["pages"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["pages"])

PAGE_PER_MIN = 600


async def _site_for_key(db: AsyncSession, key: str, origin: Optional[str]) -> store.Website:
    site = await store.get_website_by_public_key(db, (key or "").strip())
    if site is None or site.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid_widget_key")
    # Server-side callers (the Next.js adapter) send no Origin; browsers must be on the site.
    if origin and not _origin_allowed(site, origin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "origin_not_allowed")
    return site


def _signals(q: dict[str, str], path: str) -> Signals:
    return Signals.from_dict({k: q.get(k) for k in ("utm_source", "utm_medium", "utm_campaign", "utm_term",
                                                    "referrer", "q")},
                             page=path, lang="hi" if q.get("lang") == "hi" else "en",
                             persona=(q.get("persona") or "")[:40])


async def _page(request: Request, db: AsyncSession, site: store.Website, path: str) -> dict[str, Any]:
    from app.transport import guard

    if not guard._limiter.allow(f"pages:{site.site_key}", PAGE_PER_MIN):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
    q = dict(request.query_params)
    ua = q.get("ua") or request.headers.get("user-agent")  # the adapter forwards the visitor's UA
    settings = get_settings()
    out = await serve_page(
        db, request.app.state.runtime, site.site_key, path=path, sig=_signals(q, path),
        fbv=q.get("fbv"), bot=is_bot(ua, False), domain=site.domain or "",
        api_base=settings.public_api_url, public_key=site.public_key or "")
    # What a host page loads next to the HTML (the Next.js adapter uses these).
    out["scripts"] = {"composed": f"{settings.widget_sdk_base.rstrip('/')}/fluid-buddha-composed.global.js",
                      "loader": f"{settings.public_api_url.rstrip('/')}/widget/loader.js",
                      "key": site.public_key or ""}
    return out


@public.get("/experience/page")
async def composed_page(request: Request, key: str, path: str = "/") -> dict:
    async with session_scope() as db:
        site = await _site_for_key(db, key, request.headers.get("origin"))
        return await _page(request, db, site, path)


@public.post("/experience/lead")
async def form_lead(request: Request, background: BackgroundTasks):
    """The enquiry form of a server-rendered page, without JavaScript."""
    from app.leads import delivery, store as leads
    from app.routes.leads import LEAD_RATE_PER_MIN, LeadRequest
    from app.transport import guard

    form = await request.form()
    values = {str(k): str(v)[:2000] for k, v in form.items() if not str(k).startswith("_") and k != "key"}
    async with session_scope() as db:
        site = await _site_for_key(db, str(form.get("key") or ""), request.headers.get("origin"))
        if not guard._limiter.allow(f"leads:{site.site_key}", LEAD_RATE_PER_MIN):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
        body = LeadRequest(key=site.public_key, values=dict(list(values.items())[:20]))
        try:
            lead = await leads.create_lead(db, site_key=site.site_key, lead=body.to_lead(), session_id=None,
                                           source="form")
        except leads.LeadError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    background.add_task(delivery.deliver_lead, lead)
    back = str(form.get("_return") or request.headers.get("referer") or "")
    parts = urlsplit(back)
    domain = (site.domain or "").lower().removeprefix("https://").removeprefix("http://").strip("/")
    if back and (not parts.netloc or parts.netloc.lower() in (domain, f"www.{domain}")):
        return RedirectResponse(back.split("#")[0] + "#sent", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse("<!doctype html><p>Thank you — we'll be in touch.</p>")


@public.get("/g/{site_key}/{path:path}", response_class=HTMLResponse)
async def hosted_page(site_key: str, path: str, request: Request) -> HTMLResponse:
    from app.experience.ssr import render_document

    settings = get_settings()
    async with session_scope() as db:
        site = await store.get_website_by_site_key(db, site_key)
        if site is None or site.status != "active":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        page = await _page(request, db, site, "/" + path)
    if page.get("status") != 200:
        return HTMLResponse("<!doctype html><title>Not found</title><p>No page here.</p>", status_code=404,
                            headers={"X-Robots-Tag": "noindex"})
    sdk = settings.widget_sdk_base.rstrip("/")
    api = settings.public_api_url.rstrip("/")
    composed = f'<script src="{sdk}/fluid-buddha-composed.global.js" defer></script>'
    widget = f'<script src="{api}/widget/loader.js" data-key="{site.public_key}" async></script>'
    if page.get("bundle"):
        b = page["bundle"]
        composed += f'<script type="module" src="{b["url"]}" integrity="{b["integrity"]}" crossorigin="anonymous"></script>'
    html = render_document(fragment=page["html"], head=page["head"], css=page["css"], data=page["data"],
                           composed_script=composed, widget_script=widget,
                           lang="hi" if request.query_params.get("lang") == "hi" else "en")
    origins = " ".join(sorted({o for o in (urlsplit(sdk)._replace(path="").geturl(), api,
                                           urlsplit((page.get("bundle") or {}).get("url", "")).
                                           _replace(path="").geturl()) if o}))
    csp = (f"default-src 'none'; script-src {origins}; connect-src {api} ws: wss:; style-src 'unsafe-inline'; "
           f"img-src https: data:; font-src https:; form-action {api}; frame-ancestors 'none'; base-uri 'none'")
    return HTMLResponse(html, headers={"Content-Security-Policy": csp, "X-Content-Type-Options": "nosniff",
                                       "Cache-Control": "private, no-store",
                                       "Referrer-Policy": "strict-origin-when-cross-origin"})


# ---- console: routes ----------------------------------------------------------

class RouteIn(BaseModel):
    pattern: str = Field(..., max_length=200)
    title: str = Field("", max_length=120)
    purpose: str = Field("", max_length=400)
    enabled: bool = True
    priority: int = Field(0, ge=-100, le=100)


def _check_pattern(p: str) -> str:
    p = p.strip().lower()
    if p != "/" and p.endswith("/"):
        p = p.rstrip("/")
    if not routes.valid_pattern(p):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A route looks like /pricing, /products/:slug or /guides/*")
    return p


async def _route_view(db: AsyncSession, site_key: str, r: routes.Route) -> dict[str, Any]:
    plans = await rs.list_plans(db, site_key, page=r.pattern)
    plans = [p for p in plans if p["regions"] == [routes.PAGE_REGIONS]]
    for p in plans:
        p.pop("plan", None)
    return {**r.to_dict(), "plans": plans}


@admin.get("/routes")
async def list_site_routes(site: store.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> dict:
    return {"routes": [await _route_view(db, site.site_key, r) for r in await routes.list_routes(db, site.site_key)],
            "hosted_base": f"{get_settings().public_api_url.rstrip('/')}/g/{site.site_key}"}


@admin.post("/routes", status_code=status.HTTP_201_CREATED)
async def create_route(body: RouteIn, site: store.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    r = await routes.upsert_route(db, site.site_key, pattern=_check_pattern(body.pattern), title=body.title.strip(),
                                  purpose=body.purpose.strip(), enabled=body.enabled, priority=body.priority)
    return await _route_view(db, site.site_key, r)


@admin.put("/routes/{rid}")
async def update_route(rid: str, body: RouteIn, site: store.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> dict:
    cur = await routes.get_route(db, site.site_key, rid)
    if cur is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")
    pattern = _check_pattern(body.pattern)
    if pattern != cur.pattern:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A route's pattern can't change (its plans are keyed by it); add a new route.")
    r = await routes.upsert_route(db, site.site_key, pattern=pattern, title=body.title.strip(),
                                  purpose=body.purpose.strip(), enabled=body.enabled, priority=body.priority)
    return await _route_view(db, site.site_key, r)


@admin.delete("/routes/{rid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_route(rid: str, site: store.Website = Depends(owned_website),
                            db: AsyncSession = Depends(get_session)) -> None:
    if not await routes.delete_route(db, site.site_key, rid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")


class CanonicalIn(BaseModel):
    plan: Optional[str] = None


@admin.put("/routes/{rid}/canonical")
async def put_canonical(rid: str, body: CanonicalIn, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    r = await routes.set_canonical(db, site.site_key, rid, body.plan)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route or page plan not found (blocked plans can't be canonical)")
    return await _route_view(db, site.site_key, r)


class GenerateIn(BaseModel):
    family: Optional[str] = Field(None, max_length=40)
    path: Optional[str] = Field(None, max_length=300)


@admin.post("/routes/{rid}/generate", status_code=status.HTTP_201_CREATED)
async def generate_page(rid: str, body: GenerateIn, request: Request, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    from app.design.system import ensure_design, load_design_system
    from app.experience.preview import render_preview
    from app.orchestrator.profile import profile_for

    rt = request.app.state.runtime
    route = await routes.get_route(db, site.site_key, rid)
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Route not found")
    path = body.path or route.pattern.replace("/*", "").replace(":", "")
    params = route.match(path) or {}
    sig = Signals.from_dict({}, page=path)
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
    content = await _content_version(db, site.site_key)
    key = rs.plan_cache_key(family=intent.family, persona="", lang="en", page=route.pattern,
                            regions=[routes.PAGE_REGIONS], content_version=content,
                            manifest_version=load_manifest(site.site_key).version)
    row = await build_and_store_page(db, rt, site.site_key, route, params, intent, sig, key=key, content=content)
    await ensure_design(site.site_key)
    ctx = {"site_key": site.site_key, "currency": profile_for(site.site_key).currency, "lang": "en",
           "persona": "", "page": path, "route": params}
    sections, _, plan_id = await bind_page(db, rt, site.site_key, row["plan"], ctx)
    return {**row, "intent": intent.to_dict(), "plan_id": plan_id,
            "preview_html": render_preview({s["id"]: s for s in sections}, load_design_system(site.site_key),
                                           title=route.title or route.pattern)}


# ---- console: entities ----------------------------------------------------------

@admin.get("/entities")
async def entity_types(site: store.Website = Depends(owned_website), db: AsyncSession = Depends(get_session)) -> dict:
    return {"types": await ents.entity_types(db, site.site_key)}


@admin.get("/entities/{etype}")
async def list_entities(etype: str, offset: int = 0, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> dict:
    return {"records": await ents.list_entities(db, site.site_key, etype, limit=100, offset=offset)}


class EntityIn(BaseModel):
    data: dict[str, Any]


@admin.put("/entities/{etype}/{key}")
async def put_entity(etype: str, key: str, body: EntityIn, site: store.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    k = ents.clean_key(key)
    problem = ents.check_record(etype, k, body.data)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    await ents.upsert_entities(db, site.site_key, etype, [(k, body.data)])
    return await ents.get_entity(db, site.site_key, etype, k) or {}


@admin.delete("/entities/{etype}/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(etype: str, key: str, site: store.Website = Depends(owned_website),
                        db: AsyncSession = Depends(get_session)) -> None:
    if not await ents.delete_entity(db, site.site_key, etype, key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")


class ImportIn(BaseModel):
    type: str = Field(..., max_length=40)
    format: str = Field("json", pattern="^(json|csv)$")
    key_field: str = Field("slug", max_length=60)
    content: str = Field(..., max_length=2_000_000)


@admin.post("/entities/import")
async def import_entities(body: ImportIn, site: store.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> dict:
    if not ents.TYPE_RE.match(body.type):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A type is a capitalised name such as Product")
    records, problems = ents.parse_import(body.content, body.format, body.key_field)
    ok = [(k, d) for k, d in records if not ents.check_record(body.type, k, d)]
    problems += [ents.check_record(body.type, k, d) for k, d in records if ents.check_record(body.type, k, d)]
    n = await ents.upsert_entities(db, site.site_key, body.type, ok, source="import") if ok else 0
    return {"imported": n, "problems": problems[:20]}


# ---- console: connectors ----------------------------------------------------------

class ConnectorIn(BaseModel):
    kind: str = Field(..., pattern="^(json_feed|wordpress)$")
    name: str = Field("", max_length=80)
    url: str = Field(..., max_length=1000)
    entity_type: str = Field(..., max_length=40)
    items_path: str = Field("", max_length=200)
    key_field: str = Field("slug", max_length=100)
    fields: dict[str, str] = Field(default_factory=dict, max_length=30)


@admin.get("/connectors")
async def list_connectors(site: store.Website = Depends(owned_website),
                          db: AsyncSession = Depends(get_session)) -> dict:
    return {"connectors": await ents.list_connectors(db, site.site_key)}


@admin.post("/connectors", status_code=status.HTTP_201_CREATED)
async def create_connector(body: ConnectorIn, site: store.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> dict:
    if not ents.TYPE_RE.match(body.entity_type):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A type is a capitalised name such as Post")
    url = body.url.strip()
    if not url.startswith("https://"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The feed address must be https://")
    try:
        check_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    config = {"items_path": body.items_path, "key_field": body.key_field, "fields": body.fields}
    return await ents.create_connector(db, site.site_key, kind=body.kind, name=body.name.strip(), url=url,
                                       entity_type=body.entity_type, config=config)


@admin.delete("/connectors/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(cid: str, site: store.Website = Depends(owned_website),
                           db: AsyncSession = Depends(get_session)) -> None:
    if not await ents.delete_connector(db, site.site_key, cid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connector not found")


@admin.post("/connectors/{cid}/sync")
async def sync_connector(cid: str, site: store.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> dict:
    conn = await ents.get_connector(db, site.site_key, cid)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connector not found")
    return await ents.sync_connector(db, site.site_key, conn, fetch_public)
