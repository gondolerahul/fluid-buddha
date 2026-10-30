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


def normalize_component(component_type: Any, state: Any) -> tuple[str, dict]:
    """Return a ``(component_type, initial_state)`` pair safe to ship.

    Unknown types fall back to ``table``; list fields are length-capped.
    """
    ctype = component_type if component_type in KNOWN_COMPONENTS else "table"
    if not isinstance(state, dict):
        return ctype, {}
    out: dict[str, Any] = {}
    for key, val in state.items():
        out[key] = val[:_MAX_ITEMS] if isinstance(val, list) else val
    return ctype, out
