"""
Runtime page generation helpers (Extreme intelligence).

The Heavy Thinker calls ``generate_page`` to compose a full page from ordered,
typed sections. This module validates/normalises that spec and builds the
"extreme brief" injected into the system prompt (design system + site APIs +
the catalogue of section types the frontend can render).
"""
from __future__ import annotations

from typing import Any

from app.apis.registry import get_site_apis
from app.design.system import load_design_system

# Section types the frontend PageRenderer knows how to draw. Keep in sync with
# fluid-buddha-sdk/src/ui/page/PageRenderer.ts.
SECTION_TYPES: dict[str, str] = {
    "hero": "headline hero. props: {title, subtitle, cta_label?}",
    "feature_grid": "feature cards. props: {title?, items:[{title, body}]}",
    "text": "prose block. props: {title?, body}",
    "pricing_table": "pricing tiers. props: {title?, tiers:[{name, price, features:[...]}]}",
    "chart": "data viz. props: {chart_type:bar|line|pie, title?, unit?, data:[{label,value}]}",
    "flowchart": "vertical flow. props: {nodes:[{label}], edges:[{from,to}]}",
    "enquiry_form": "lead capture. props: {title?, fields:[{name,label,type}], submit_label?, operation_id?}",
    "cta": "call to action. props: {title, body?, cta_label}",
    "media": "image/logo. props: {src, alt?, caption?}",
    # M3-1: landing-page sections.
    "testimonials": "customer quotes. props: {title?, items:[{quote, name, role?}]}",
    "logos": "customer logos. props: {title?, items:[{src, alt}]}",
    "faq": "questions and answers. props: {title?, items:[{q, a}]}",
    "comparison": "side-by-side table. props: {title?, columns:[...], rows:[{label, values:[...]}]}",
    "roi_calculator": "interactive ROI estimate. props: {title?, seats?, monthly_cost?, hours_saved?, hourly_value?}",
}

_MAX_SECTIONS = 12


def normalize_page(title: Any, sections: Any) -> tuple[str, list[dict]]:
    """Coerce model output into a safe, bounded PageSpec body."""
    clean_title = str(title or "Untitled").strip()[:160]
    out: list[dict] = []
    if isinstance(sections, list):
        for s in sections:
            if not isinstance(s, dict):
                continue
            stype = str(s.get("type") or "").strip()
            if stype not in SECTION_TYPES:
                continue
            props = s.get("props")
            out.append({"type": stype, "props": props if isinstance(props, dict) else {}})
            if len(out) >= _MAX_SECTIONS:
                break
    return clean_title, out


def bindable_prompt(site_key: str) -> str:
    """The read operations a page may bind props to (Experience Plan, P0-5)."""
    ops = get_site_apis(site_key).bindable_operations()
    if not ops:
        return ""
    listed = "; ".join(
        f"{o.operation_id} — {o.summary}" + (f" (returns {o.entity})" if o.entity else "")
        for o in ops
    )
    return (
        "BINDABLE DATA — never type live values (prices, plans, stock, records) "
        "into a page. Bind the prop instead: {\"bind\": \"api:<operationId>\", "
        "\"path\": \"$.field[*]\", \"params\": {...}, \"transform\": "
        "[\"limit:3\"]}; params may use ctx.currency, ctx.lang, ctx.persona; "
        "\"map\": {\"title\": \"name\"} renames record fields to a prop's shape. "
        "Operations: " + listed + "."
    )


def build_extreme_brief(site_key: str) -> str:
    """The system-prompt addendum that grounds runtime page generation."""
    from app.experience.manifest import load_manifest  # avoids an import cycle

    ds = load_design_system(site_key)
    apis = get_site_apis(site_key)
    parts = [
        "EXTREME MODE — this site has NO authored pages. When the visitor asks to "
        "see something, BUILD it with `generate_page`, grounding ALL copy in "
        "`query_cortex` results (never invent facts, prices, or features).",
        ds.to_prompt(),
        load_manifest(site_key).to_prompt(),
    ]
    bind = bindable_prompt(site_key)
    if bind:
        parts.append(bind)
    api_prompt = apis.to_prompt()
    if api_prompt:
        parts.append(api_prompt)
    return "\n".join(parts)
