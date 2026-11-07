"""
The site's agent endpoint for AI assistants (M3-2).

Public (the website's widget key in the path; off until the site switches
agent access on; rate-limited, under the site's daily spend cap; every call
logged as agent traffic):

    POST /mcp/{key}                    MCP over streamable HTTP (JSON-RPC 2.0)
    GET  /sites/{key}/llms.txt         what the site is and how assistants can ask it
    GET  /sites/{key}/openapi.json     the REST endpoints below, for tool-calling agents
    POST /agent/{key}/ask              {question} -> a grounded answer with sources
    GET  /agent/{key}/offerings        plans and prices
    GET  /sites/{key}/views            pages with views; ?path=/pricing → that page's view (Phase 5)
    GET  /sites/{key}/views/{plan_id}  a view (JSON, or markdown with ?format=md / Accept)
    GET  /sites/{key}/views.schema.json
    POST /sites/{key}/views/{plan_id}/actions/{action}   {inputs, confirm_code} (Bearer token)

Console (reads Viewer; changes Admin; audit-logged):

    GET    /tenant/websites/{id}/agent-access     switch, endpoints, tokens, traffic
    PUT    /tenant/websites/{id}/agent-access     {enabled}
    POST   /tenant/websites/{id}/agent-tokens     {name, scopes} -> the token, once
    DELETE /tenant/websites/{id}/agent-tokens/{token_id}
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import mcp, store as agents, tools
from app.auth import team
from app.auth.security import current_member
from app.config import get_settings
from app.db import get_session, session_scope
from app.tenancy import store as tenancy
from app.tenancy.deps import owned_website
from app.transport import guard

public = APIRouter(tags=["agent"])
admin = APIRouter(prefix="/tenant/websites/{website_id}", tags=["agent"])

AGENT_RATE_PER_MIN = 30   # per site and client address


def _base() -> str:
    return get_settings().public_api_url.rstrip("/")


def endpoints(key: str) -> dict[str, str]:
    b = _base()
    return {"mcp": f"{b}/mcp/{key}", "llms_txt": f"{b}/sites/{key}/llms.txt",
            "openapi": f"{b}/sites/{key}/openapi.json", "ask": f"{b}/agent/{key}/ask",
            "views": f"{b}/sites/{key}/views"}


async def _site(key: str) -> dict[str, Any]:
    async with session_scope() as db:
        site = await agents.site_for_key(db, key)
    if site is None or not site["agent_access"]:
        # One answer for "no such site" and "not switched on": nothing to probe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No agent endpoint here.")
    return site


def _origin_ok(request: Request, site: dict[str, Any]) -> bool:
    """MCP servers must check Origin (DNS rebinding): a browser page may only
    call from the site's own domain. Assistants send no Origin."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    host = urlsplit(origin).hostname or ""
    domain = (site.get("domain") or "").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def _client(request: Request, hint: Optional[str] = None) -> str:
    return (hint or request.headers.get("user-agent") or "unknown")[:120]


async def _limit(request: Request, site: dict[str, Any], *, model_call: bool) -> Optional[str]:
    ip = request.client.host if request.client else "?"
    if not guard._limiter.allow(f"agent:{site['site_key']}:{ip}", AGENT_RATE_PER_MIN):
        return guard.RATE_LIMITED
    if model_call:
        async with session_scope() as db:
            return await guard.check_public_budget(db, site["site_key"], get_settings())
    return None


async def _pages(site: dict[str, Any]) -> list[dict[str, Any]]:
    async with session_scope() as db:
        rows = (await db.execute(text(
            "SELECT name, content FROM tenant_sources WHERE website_id = :w AND kind = 'url' "
            "ORDER BY created_at LIMIT 40"), {"w": site["id"]})).mappings().all()
    out = []
    for r in rows:
        parts = urlsplit(r["content"] or "")
        if parts.scheme in ("http", "https") and parts.netloc:
            out.append({"uri": f"https://{parts.netloc}{parts.path or '/'}", "path": parts.path or "/",
                        "name": (r["name"] or parts.path or "/")[:120]})
    return out


async def _log(site: dict[str, Any], **kw: Any) -> None:
    async with session_scope() as db:
        await agents.log(db, site["site_key"], **kw)


# ---- MCP -----------------------------------------------------------------------------------

@public.post("/mcp/{key}")
async def mcp_post(key: str, request: Request) -> Response:
    site = await _site(key)
    if not _origin_ok(request, site):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")
    version = request.headers.get("mcp-protocol-version")
    if version and version not in mcp.SUPPORTED_VERSIONS:
        return JSONResponse(mcp.error(None, mcp.INVALID_REQUEST, f"Unsupported protocol version {version}"), 400)
    try:
        msg = mcp.parse(await request.body())
    except mcp.RpcError as exc:
        return JSONResponse(mcp.error(None, exc.code, exc.message), 400)
    if isinstance(msg, list):
        return JSONResponse(mcp.error(None, mcp.INVALID_REQUEST, "Batches aren't supported"), 400)

    method = msg.get("method") if isinstance(msg, dict) else None
    model_call = method in ("tools/call", "resources/read")
    blocked = await _limit(request, site, model_call=model_call)
    if blocked:
        return JSONResponse(mcp.error(msg.get("id") if isinstance(msg, dict) else None, -32000,
                                      guard.REFUSAL_MESSAGES.get(blocked, blocked)), 429)

    auth = request.headers.get("authorization") or ""
    token = None
    if auth.lower().startswith("bearer "):
        async with session_scope() as db:
            token = await agents.verify(db, site["site_key"], auth[7:].strip())
    if token and "actions" in token["scopes"]:
        from app.routes.actions import ensure_extras
        await ensure_extras(site["site_key"])   # the site's actions, as tools
    hint = None
    if method == "initialize" and isinstance(msg.get("params"), dict):
        info = msg["params"].get("clientInfo") or {}
        hint = " ".join(str(info.get(k) or "") for k in ("name", "version")).strip() or None
    ctx = mcp.Context(rt=request.app.state.runtime, site=site, token=token,
                      client=_client(request, hint), pages=await _pages(site) if method and method.startswith("resources") else [])
    response, what, ok = await mcp.handle(ctx, msg)
    if method in ("initialize", "tools/call", "resources/read"):
        err = (response or {}).get("error", {}).get("message") if response else None
        if not err and response and (response.get("result") or {}).get("isError"):
            err = str(((response["result"].get("structuredContent") or {}).get("message")
                       or (response["result"].get("structuredContent") or {}).get("error") or ""))[:300] or None
        if what == "run_view_action":  # task analytics: the outcome is the step
            what = f"view_action.{ctx.meta.get('status') or 'refused'}"
        await _log(site, kind="mcp", tool=what, client=ctx.client, token_id=token["id"] if token else None,
                   ok=ok, error=err, plan_id=ctx.meta.get("plan_id"), action=ctx.meta.get("action"))
    if response is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)
    return JSONResponse(response)


@public.get("/mcp/{key}")
async def mcp_get(key: str) -> Response:
    await _site(key)
    # No server-initiated stream: this server only answers requests.
    return Response(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, headers={"Allow": "POST"})


# ---- llms.txt, OpenAPI, REST -------------------------------------------------------------

@public.get("/sites/{key}/llms.txt", response_class=PlainTextResponse)
async def llms_txt(key: str, request: Request) -> PlainTextResponse:
    from app.orchestrator.profile import ensure_profile

    site = await _site(key)
    profile = await ensure_profile(site["site_key"])
    pages = await _pages(site)
    e = endpoints(key)
    lines = [f"# {profile.company_name or site['name']}", ""]
    lines += [f"> Answers about {profile.company_name or site['name']} come from its own website content, "
              "through its FluidBuddha agent.", ""]
    if site.get("domain"):
        lines += [f"Website: https://{site['domain']}", ""]
    if pages:
        lines += ["## Pages", ""] + [f"- [{p['name']}]({p['uri']})" for p in pages] + [""]
    from app.agents import views

    listed = (await views.list_views(site))["views"]
    if listed:
        lines += ["## Views", "", "Each page as people see it, as text (markdown):", ""]
        lines += [f"- [{v['title']}]({v['markdown']})" + (f": {v['purpose']}" if v.get("purpose") else "")
                  for v in listed if v.get("markdown")] + [""]
    lines += ["## For AI assistants", "",
              f"- [MCP server]({e['mcp']}): tools search_knowledge, get_page, list_offerings, list_views, "
              "get_view (streamable HTTP, no sign-in needed to read)",
              f"- [Views]({_base()}/sites/{key}/views): each page as structured data "
              f"([schema]({_base()}/sites/{key}/views.schema.json)); actions run under the site's "
              "confirmation rules",
              f"- [OpenAPI description]({e['openapi']}): POST {e['ask']} with {{\"question\": \"…\"}}",
              "- Grounded answers with sources; for anything that acts (leads, payments), ask the company "
              "for a token.", ""]
    await _log(site, kind="llms", tool="llms.txt", client=_client(request))
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8",
                             headers={"Cache-Control": "public, max-age=3600"})


# ---- views (Phase 5) --------------------------------------------------------------------------

def _wants_markdown(request: Request, fmt: Optional[str]) -> bool:
    return fmt == "md" or "text/markdown" in (request.headers.get("accept") or "")


@public.get("/sites/{key}/views.schema.json")
async def views_schema(key: str) -> JSONResponse:
    from app.experience.agentview import VIEW_SCHEMA

    await _site(key)
    return JSONResponse(VIEW_SCHEMA, headers={"Cache-Control": "public, max-age=86400"})


@public.get("/sites/{key}/views")
async def views_index(key: str, request: Request, path: Optional[str] = None,
                      format: Optional[str] = None) -> Response:
    from app.agents import views

    site = await _site(key)
    blocked = await _limit(request, site, model_call=False)
    if blocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
    if not path:
        out = await views.list_views(site)
        await _log(site, kind="view", tool="list_views", client=_client(request))
        return JSONResponse(out)
    view = await views.load_view(request.app.state.runtime, site, path=path)
    if view is None:
        await _log(site, kind="view", tool="get_view", client=_client(request), ok=False, error="no view")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No view for that path.")
    await _log(site, kind="view", tool="get_view", client=_client(request), plan_id=view["plan_id"])
    return _view_response(request, view, format)


@public.get("/sites/{key}/views/{plan_id}")
async def view_by_id(key: str, plan_id: str, request: Request, path: Optional[str] = None,
                     format: Optional[str] = None) -> Response:
    from app.agents import views

    site = await _site(key)
    blocked = await _limit(request, site, model_call=False)
    if blocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
    view = await views.load_view(request.app.state.runtime, site, plan_id=plan_id, path=path)
    if view is None:
        await _log(site, kind="view", tool="get_view", client=_client(request), ok=False, error="no view",
                   plan_id=plan_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such view.")
    await _log(site, kind="view", tool="get_view", client=_client(request), plan_id=view["plan_id"])
    return _view_response(request, view, format)


def _view_response(request: Request, view: dict[str, Any], fmt: Optional[str]) -> Response:
    from app.agents import views

    headers = {"Cache-Control": "private, max-age=60", "Link": f'<{view["links"]["markdown"]}>; rel="alternate"; '
                                                                'type="text/markdown"'}
    if _wants_markdown(request, fmt):
        return PlainTextResponse(views.markdown(view), media_type="text/markdown; charset=utf-8", headers=headers)
    return JSONResponse(view, headers=headers)


class ViewActionIn(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    confirm_code: str = Field("", max_length=64)


@public.post("/sites/{key}/views/{plan_id}/actions/{action}")
async def view_action(key: str, plan_id: str, action: str, body: ViewActionIn, request: Request) -> dict:
    from app.agents import views

    site = await _site(key)
    if not _origin_ok(request, site):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")
    blocked = await _limit(request, site, model_call=False)
    if blocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
    auth = request.headers.get("authorization") or ""
    token = None
    if auth.lower().startswith("bearer "):
        async with session_scope() as db:
            token = await agents.verify(db, site["site_key"], auth[7:].strip())
    if token and "actions" in token["scopes"]:
        from app.routes.actions import ensure_extras
        await ensure_extras(site["site_key"])
    out = await views.run(request.app.state.runtime, site, plan_id, action, body.inputs, token, body.confirm_code)
    await _log(site, kind="rest", tool=f"view_action.{out['status']}", client=_client(request),
               token_id=token["id"] if token else None, ok=out["status"] in ("done", "needs_confirmation"),
               error=out.get("message") if out["status"] in ("refused", "failed") else None,
               plan_id=plan_id, action=action)
    if out["status"] == "refused" and out.get("message", "").startswith("This needs a token"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, out["message"])
    return out


@public.get("/sites/{key}/openapi.json")
async def openapi_doc(key: str) -> JSONResponse:
    site = await _site(key)
    e = endpoints(key)
    answer = {"type": "object", "properties": {
        "answer": {"type": "string"}, "found": {"type": "boolean"},
        "sources": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "url": {"type": "string"}, "route": {"type": "string"}}}}}}
    doc = {
        "openapi": "3.1.0",
        "info": {"title": f"{site['name']} — ask the website", "version": "1.0.0",
                 "description": "Grounded answers from this website's own content, with sources."},
        "servers": [{"url": _base()}],
        "paths": {
            f"/agent/{key}/ask": {"post": {
                "operationId": "askWebsite", "summary": "Ask a question about the company and its products",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"question": {"type": "string", "maxLength": 1000}},
                    "required": ["question"]}}}},
                "responses": {"200": {"description": "The answer", "content": {
                    "application/json": {"schema": answer}}}, "429": {"description": "Too many questions"}}}},
            f"/agent/{key}/offerings": {"get": {
                "operationId": "listOfferings", "summary": "Plans, products and prices",
                "responses": {"200": {"description": "Offerings", "content": {
                    "application/json": {"schema": answer}}}}}},
        },
        "externalDocs": {"url": e["llms_txt"]},
    }
    return JSONResponse(doc, headers={"Cache-Control": "public, max-age=3600"})


class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


@public.post("/agent/{key}/ask")
async def rest_ask(key: str, body: AskIn, request: Request) -> dict:
    site = await _site(key)
    if not _origin_ok(request, site):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")
    blocked = await _limit(request, site, model_call=True)
    if blocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
    try:
        out = await tools.ask(request.app.state.runtime, site, body.question)
    except tools.ToolError as exc:
        await _log(site, kind="rest", tool="ask", client=_client(request), ok=False, error=str(exc))
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    await _log(site, kind="rest", tool="ask", client=_client(request))
    return out


@public.get("/agent/{key}/offerings")
async def rest_offerings(key: str, request: Request) -> dict:
    site = await _site(key)
    blocked = await _limit(request, site, model_call=True)
    if blocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, blocked)
    out = await tools.list_offerings(request.app.state.runtime, site)
    await _log(site, kind="rest", tool="offerings", client=_client(request))
    return out


# ---- console ----------------------------------------------------------------------------

class AccessIn(BaseModel):
    enabled: bool


class TokenIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    scopes: list[str] = Field(default_factory=list, max_length=2)


@admin.get("/agent-access")
async def get_access(site: tenancy.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    enabled = (await db.execute(text("SELECT agent_access FROM tenant_websites WHERE id = :id"),
                                {"id": site.id})).scalar()
    return {"enabled": bool(enabled),
            "endpoints": endpoints(site.public_key) if site.public_key else None,
            "tokens": await agents.list_tokens(db, site.site_key),
            "traffic": await agents.traffic(db, site.site_key),
            "funnel": await agents.funnel(db, site.site_key)}


@admin.get("/agent-views")
async def agent_views(request: Request, site: tenancy.Website = Depends(owned_website)) -> dict:
    """Each route's view as agents get it: its actions and their agent policy (Phase 5)."""
    from app.agents import views

    if not site.public_key:
        return {"views": []}
    info = {"id": site.id, "tenant_id": getattr(site, "tenant_id", None), "site_key": site.site_key, "name": site.name,
            "domain": site.domain, "intelligence": getattr(site, "intelligence", "advance"), "agent_access": True,
            "public_key": site.public_key}
    out = []
    for v in (await views.list_views(info))["views"]:
        view = await views.load_view(request.app.state.runtime, info, path=v["path"]) if v.get("markdown") else None
        out.append({**v, "plan_id": view["plan_id"] if view else None,
                    "preview": f"{_base()}/g/{site.site_key}{v['path']}?fbmode=plain" if v.get("markdown") else None,
                    "actions": view["actions"] if view else [],
                    "regions": len(view["regions"]) if view else 0})
    return {"views": out}


@admin.put("/agent-access")
async def put_access(body: AccessIn, site: tenancy.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    if body.enabled and not site.public_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create a widget key first (Install tab).")
    await db.execute(text("UPDATE tenant_websites SET agent_access = :e WHERE id = :id"),
                     {"e": body.enabled, "id": site.id})
    await db.commit()
    return {"enabled": body.enabled}


@admin.post("/agent-tokens", status_code=status.HTTP_201_CREATED)
async def create_token(body: TokenIn, site: tenancy.Website = Depends(owned_website),
                       m: team.Member = Depends(current_member),
                       db: AsyncSession = Depends(get_session)) -> dict:
    scopes = [s for s in body.scopes if s in agents.SCOPES]
    if not scopes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick what it may do: leads, actions.")
    row, token = await agents.create_token(db, site.site_key, body.name.strip(), scopes, m.user_id)
    await db.commit()
    return {**row, "token": token}


@admin.delete("/agent-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(token_id: uuid.UUID, site: tenancy.Website = Depends(owned_website),
                       db: AsyncSession = Depends(get_session)) -> None:
    if not await agents.revoke_token(db, site.site_key, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such token")
    await db.commit()
