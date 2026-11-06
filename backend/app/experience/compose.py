"""
Compose a page from a ``generate_page`` tool call (P0-5).

Accepts the plan form (``regions`` with bindings) or the v1.0 form
(``sections`` of built-in types, converted to ``fb.<type>`` regions), then
validate → bind → a ``PageSpec`` whose sections keep the v1.0 wire shape plus
``id`` / ``component`` / ``state``.

The tool result returned to the model carries ids, counts and problems only —
never bound values (strategy §4.6, model isolation).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from app.apis.registry import get_site_apis
from app.experience.binding import bind_plan
from app.experience.manifest import is_wc_renderer, load_manifest
from app.experience.plan import validate_plan
from app.orchestrator.result import PageSpec


def regions_from_sections(sections: Any) -> list[dict[str, Any]]:
    """v1.0 ``[{type, props}]`` → plan regions over the default manifest."""
    out: list[dict[str, Any]] = []
    if isinstance(sections, list):
        for s in sections:
            if isinstance(s, dict) and s.get("type"):
                region: dict[str, Any] = {
                    "component": f"fb.{str(s.get('type')).strip()}",
                    "props": s.get("props") if isinstance(s.get("props"), dict) else {},
                }
                if s.get("id"):
                    region["id"] = s["id"]
                out.append(region)
    return out


async def compose_page(
    args: Mapping[str, Any],
    *,
    site_key: str,
    sync_id: str,
    ctx: Optional[Mapping[str, Any]] = None,
    source: str = "planner",
    bridge: Any = None,
) -> tuple[PageSpec, dict[str, Any]]:
    manifest = load_manifest(site_key)
    registry = get_site_apis(site_key)

    regions = args.get("regions")
    if not isinstance(regions, list):
        regions = regions_from_sections(args.get("sections"))
    raw = {
        "title": args.get("title"),
        "regions": regions,
        "actions": args.get("actions"),
        "intent": args.get("intent"),
        "layout": args.get("layout"),
        "policies": args.get("policies"),
        "provenance": {"source": source, "manifest": manifest.source,
                       "manifest_version": manifest.version},
    }
    report = validate_plan(raw, manifest=manifest, catalogue=registry, site_key=site_key)
    from app.db import session_scope
    from app.experience.resolvers import make_resolver

    async with session_scope() as db:  # entity: / content: bindings (P2-6)
        bound = await bind_plan(report.plan, manifest=manifest, registry=registry, ctx=ctx,
                                resolve=make_resolver(db, None, site_key, bridge=bridge))

    page = PageSpec(
        sync_id=sync_id,
        title=report.plan.title,
        sections=[b.to_section() for b in bound],
        plan_id=report.plan.plan_id,
        plan=report.plan.to_dict(),
        actions=[a.to_dict() for a in report.plan.actions],
        bundle=(manifest.bundle
                if any(is_wc_renderer(b.renderer) for b in bound) else None),
    )
    tool_result: dict[str, Any] = {
        "ok": bool(bound),
        "sync_id": sync_id,
        "plan_id": report.plan.plan_id,
        "region_count": len(bound),
        "regions": [{"id": b.id, "component": b.component, "state": b.state} for b in bound],
        # Kept for v1.0 prompts/tests that read it.
        "section_count": len(bound),
    }
    if report.problems:
        tool_result["problems"] = report.problems[:12]
    if report.dropped:
        tool_result["dropped"] = report.dropped[:12]
    return page, tool_result
