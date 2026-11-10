"""
Views for agents (generative experience Phase 5): loading a page's view, listing
the site's views, and running a view's actions. The agent endpoint (REST, MCP,
``llms.txt``) and the console call these; the rules live in
``app.experience.agentview``.
"""
from __future__ import annotations

from typing import Any, Optional

from app.config import get_settings
from app.db import session_scope
from app.experience import agentview


def _base() -> str:
    return get_settings().public_api_url.rstrip("/")


def _links(site: dict[str, Any], plan_id: str, url: str, path: str) -> dict[str, str]:
    b, key = _base(), site["public_key"]
    return {"json": f"{b}/sites/{key}/views/{plan_id}", "markdown": f"{b}/sites/{key}/views/{plan_id}?format=md",
            "page": url if url.startswith("https://") else f"{b}/g/{site['site_key']}{path}",
            "schema": f"{b}/sites/{key}/views.schema.json"}


async def list_views(site: dict[str, Any]) -> dict[str, Any]:
    """The site's routes. Concrete paths link to their view; patterns with
    parameters say how to ask for one."""
    from app.experience import routes_store as routes

    async with session_scope() as db:
        rows = [r for r in await routes.list_routes(db, site["site_key"]) if r.enabled]
    b, key = _base(), site["public_key"]
    out = []
    for r in rows:
        concrete = ":" not in r.pattern and "*" not in r.pattern
        v: dict[str, Any] = {"path": r.pattern, "title": r.title or r.pattern, "purpose": r.purpose}
        if concrete:
            v["view"] = f"{b}/sites/{key}/views?path={r.pattern}"
            v["markdown"] = f"{b}/sites/{key}/views?path={r.pattern}&format=md"
        else:
            v["note"] = f"Ask for a concrete path, e.g. {b}/sites/{key}/views?path=" + \
                r.pattern.replace("/*", "/example").replace(":", "")
        out.append(v)
    return {"views": out}


async def load_view(rt: Any, site: dict[str, Any], *, path: Optional[str] = None, plan_id: Optional[str] = None,
                    html: bool = False) -> Optional[dict[str, Any]]:
    """A view by path (the page a visitor gets by default) or by plan id."""
    from app.design.system import ensure_design, load_design_system
    from app.experience import routes_store as routes
    from app.experience.intent import Signals
    from app.experience.manifest import ensure_manifest
    from app.experience.pages import _description, bind_page, canonical_url, plan_by_plan_id, serve_page
    from app.experience.regions_store import normalize_page
    from app.experience.ssr import render_document, render_fragment, stylesheet
    from app.orchestrator.profile import profile_for

    from app.routes.actions import ensure_extras

    site_key = site["site_key"]
    await ensure_extras(site_key)  # the site's actions, which view actions point at
    if path is not None:
        path = str(path)[:200]
        if not path.startswith("/") or any(c in path for c in "\n\r\t <>\"'"):
            return None
        path = normalize_page(path)
    async with session_scope() as db:
        if plan_id:
            row = await plan_by_plan_id(db, site_key, str(plan_id))
            if row is None:
                return None
            path = path or row["page"]
            matched = await routes.match_route(db, site_key, path)
            route_pattern, params = (matched[0].pattern, matched[1]) if matched else (row["page"], {})
            await ensure_manifest(site_key)
            ctx = {"site_key": site_key, "currency": profile_for(site_key).currency, "lang": "en",
                   "persona": "", "page": path, "route": params}
            sections, _, pid = await bind_page(db, rt, site_key, row["plan"], ctx)
            plan = row["plan"]
            title = str(plan.get("title") or (matched[0].title if matched else "") or site["name"])
            lang = "en"
        else:
            if not path:
                return None
            out = await serve_page(db, rt, site_key, path=path, sig=Signals(page=path), bot=True,
                                   domain=site.get("domain") or "", api_base=_base(),
                                   public_key=site.get("public_key") or "", mode="agent", include_sections=True)
            if out.get("status") != 200:
                return None
            sections, plan, pid = out["_sections"], out["_plan"], out["plan_id"]
            title, route_pattern, lang = out["head"]["title"], out["route"], "en"
    url = canonical_url(site.get("domain") or "", path)
    desc = _description(sections)
    prof = profile_for(site_key)
    ld = agentview.json_ld(sections, title=title, description=desc, url=url, org=prof.company_name or site["name"],
                           currency=prof.currency or "")
    view = agentview.build_view(plan=plan, sections=sections, site=site, plan_id=pid, title=title, url=url,
                                path=path, route=route_pattern, lang=lang, links=_links(site, pid, url, path), ld=ld)
    if html:
        await ensure_design(site_key)
        design = load_design_system(site_key)
        frag = render_fragment(sections, plan_id=pid, title=title, flow=plan.get("flow"), mode="agent")
        view["_html"] = render_document(fragment=frag, head={"title": title, "description": desc,
                                                             "robots": "noindex"},
                                        css=stylesheet(design), data={"plan_id": pid})
    return view


def markdown(view: dict[str, Any]) -> str:
    return agentview.view_markdown(view)


async def run(rt: Any, site: dict[str, Any], plan_id: str, action: str, inputs: Any,
              token: Optional[dict[str, Any]], confirm_code: str = "") -> dict[str, Any]:
    view = await load_view(rt, site, plan_id=plan_id)
    if view is None:
        return {"status": "refused", "message": "No such view."}
    async with session_scope() as db:
        return await agentview.run_action(db, site, view, action, inputs, token, confirm_code)
