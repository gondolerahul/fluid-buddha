"""
Server-side normalisation for ``render_component`` payloads (mirrors
``pagegen.normalize_page``).

Keeps LLM-authored component state safe and bounded: snaps unknown types to a
table and caps any list-valued field so a runaway generation can't ship a
10k-node diagram to the frontend.
"""
from __future__ import annotations

from typing import Any

_MAX_ITEMS = 48

KNOWN_COMPONENTS = {
    "flowchart", "workflow", "component_diagram", "graph", "chart",
    "roi_calculator", "table", "mind_map", "timeline", "sankey",
    "configurator", "scenario_simulator", "tabs",
}


MONEY_COMPONENTS = {"roi_calculator", "configurator", "scenario_simulator"}


def normalize_component(component_type: Any, state: Any,
                        site_key: str | None = None) -> tuple[str, dict]:
    """Return a ``(component_type, initial_state)`` pair safe to ship.

    A site's own component (M2-8) is checked against its props schema and
    expanded to the built-in component it's made of (or a sandboxed embed);
    a props mismatch raises ``PropsError`` (a ValueError). Unknown types fall
    back to ``table``; list fields are length-capped.
    """
    if site_key and component_type not in KNOWN_COMPONENTS:
        from app.orchestrator.custom_components import components_for, render
        custom = components_for(site_key).get(str(component_type))
        if custom is not None:
            ctype, expanded = render(custom, state)
            if ctype == "embed":
                return ctype, expanded
            return _with_currency(site_key, *normalize_component(ctype, expanded))
    ctype = component_type if component_type in KNOWN_COMPONENTS else "table"
    if not isinstance(state, dict):
        return ctype, {}
    out: dict[str, Any] = {}
    for key, val in state.items():
        out[key] = val[:_MAX_ITEMS] if isinstance(val, list) else val
    return _with_currency(site_key, ctype, out) if site_key else (ctype, out)


def _with_currency(site_key: str, ctype: str, state: dict) -> tuple[str, dict]:
    """Money in the site's currency (M2-8 follow-up: ₹ for an Indian site)."""
    if ctype in MONEY_COMPONENTS and not state.get("currency"):
        from app.orchestrator.profile import profile_for
        state = {**state, "currency": profile_for(site_key).currency}
    return ctype, state
