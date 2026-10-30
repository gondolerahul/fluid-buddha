"""
Tool (function-call) declarations exposed to the Heavy Thinker.

Schemas are plain JSON-schema dicts; the Vertex client converts them to
``FunctionDeclaration``s and the mock client reads them by name.
"""
from __future__ import annotations

from app.ai.base import ToolSpec

QUERY_CORTEX = ToolSpec(
    name="query_cortex",
    description=(
        "Retrieve grounded facts from the product knowledge base. Call this "
        "before any claim about capabilities, pricing, integrations or security. "
        "Returns snippets and a confidence score."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look up."}
        },
        "required": ["query"],
    },
)

RENDER_COMPONENT = ToolSpec(
    name="render_component",
    description=(
        "Render a dynamic, strongly-typed UI component in the agent canvas to "
        "visually explain something — or an INTERACTIVE one the visitor can play "
        "with. Pair with a short spoken explanation. Choose the component_type "
        "that fits, and shape initial_state to match:\n"
        "- flowchart: vertical steps. {nodes:[{label}], edges:[{from,to}]}\n"
        "- workflow: horizontal process with branches. {steps:[{id,label,"
        "type:start|process|decision|end}], transitions:[{from,to,label}]}\n"
        "- component_diagram: architecture boxes + arrows. {components:[{id,"
        "label}], connections:[{from,to}]}\n"
        "- graph: node-link relationships. {nodes:[{id,label}], edges:[{from,to}],"
        " directed:true}\n"
        "- chart: data viz. {chart_type:bar|line|pie, title, unit, data:[{label,"
        "value}]}\n"
        "- roi_calculator: {seats, monthly_cost, hours_saved}\n"
        "- table: {headers:[...], rows:[[...]]}\n"
        "- mind_map: radial topic tree, branches expand/collapse on click. "
        "{topic, branches:[{label, children:[{label}]}]}\n"
        "- timeline: milestones on an axis, detail on hover. {events:[{date,label,"
        "detail}]}\n"
        "- sankey: weighted flows (where time/cost/traffic goes). {nodes:[{id,"
        "label,column?}], links:[{source,target,value}]}\n"
        "- configurator: sliders/toggles/selects that drive live computed outputs. "
        "{controls:[{key,label,type:slider|toggle|select,min,max,step,value,unit,"
        "options:[{label,value}]}], outputs:[{label,expr,format:currency|percent|"
        "number,unit}]}. `expr` is arithmetic over control keys, e.g. "
        "\"hours*45-monthly_cost\".\n"
        "- scenario_simulator: sliders that drive live bars for what-if analysis. "
        "{sliders:[{key,label,min,max,step,value,unit}], series:[{label,expr,"
        "format,unit}]}\n"
        "- tabs: tabbed content the visitor explores. {tabs:[{label,body}]}\n"
        "For configurator/scenario_simulator, `expr` may ONLY use control/slider "
        "keys, numbers and + - * / ( ) — nothing else."
    ),
    parameters={
        "type": "object",
        "properties": {
            "component_type": {
                "type": "string",
                "enum": [
                    "flowchart", "workflow", "component_diagram", "graph",
                    "chart", "roi_calculator", "table",
                    "mind_map", "timeline", "sankey", "configurator",
                    "scenario_simulator", "tabs",
                ],
            },
            "initial_state": {
                "type": "object",
                "description": "Component-specific data (see description for the "
                               "shape per component_type).",
            },
            "explanation_text": {"type": "string"},
        },
        "required": ["component_type", "initial_state"],
    },
)

PATCH_COMPONENT = ToolSpec(
    name="patch_component",
    description=(
        "Mutate an already-rendered component (e.g. after a barge-in correction) "
        "without recreating it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target_sync_id": {"type": "string"},
            "patch": {"type": "object"},
            "animation": {"type": "string", "enum": ["fade", "count_up", "highlight"]},
        },
        "required": ["target_sync_id", "patch"],
    },
)

NAVIGATE = ToolSpec(
    name="navigate",
    description="Navigate the visitor to a page on the site.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "e.g. /pricing"}},
        "required": ["path"],
    },
)

SCROLL_TO = ToolSpec(
    name="scroll_to",
    description=(
        "Scroll the current page. Use `direction` for relative scrolling when the "
        "visitor says things like 'scroll down a bit', 'scroll up', 'go to the "
        "top/bottom'. Use `section_id` (a section name or DOM anchor, e.g. "
        "'pricing', 'testimonials') to jump to a specific section. Provide at "
        "least one."
    ),
    parameters={
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["down", "up", "top", "bottom"],
                "description": "Relative scroll direction.",
            },
            "section_id": {
                "type": "string",
                "description": "Section name or DOM anchor to scroll to.",
            },
        },
    },
)

SET_PERSONA = ToolSpec(
    name="set_persona",
    description="Silently switch the site's persona/ICP theme to match the visitor.",
    parameters={
        "type": "object",
        "properties": {
            "persona": {
                "type": "string",
                "enum": ["startups", "solopreneurs", "medium-enterprise", "enterprise"],
            }
        },
        "required": ["persona"],
    },
)

GENERATE_PAGE = ToolSpec(
    name="generate_page",
    description=(
        "Compose and render a FULL page at runtime (Extreme tier — the host site "
        "has no authored pages). Ground ALL copy in `query_cortex` results and "
        "keep visual styling to the brand design system (the frontend themes it "
        "automatically). Provide an ordered list of typed sections."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "sections": {
                "type": "array",
                "description": "Ordered sections; each {type, props}. See the "
                               "PAGE SECTIONS list in context for types + props.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "props": {"type": "object"},
                    },
                    "required": ["type"],
                },
            },
        },
        "required": ["title", "sections"],
    },
)

CALL_SITE_API = ToolSpec(
    name="call_site_api",
    description=(
        "Call one of the site's ingested APIs to pull live data or submit an "
        "enquiry. Use the EXACT operation_id from the SITE APIS list in context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation_id": {"type": "string"},
            "params": {"type": "object"},
        },
        "required": ["operation_id"],
    },
)

THINKER_TOOLS = [
    QUERY_CORTEX,
    RENDER_COMPONENT,
    PATCH_COMPONENT,
    NAVIGATE,
    SCROLL_TO,
    SET_PERSONA,
]

# Names that are client-side effects (recorded + acked) vs. server retrieval.
ACTION_TOOLS = {"navigate", "scroll_to", "set_persona"}
COMPONENT_TOOLS = {"render_component", "patch_component"}

# ---------------------------------------------------------------------------
# Intelligence-level gating — the set of tools offered to the Heavy Thinker
# grows with the configured capability tier (see the A2UI "intelligence levels").
#   basic   : text chat + redirect/scroll only
#   high    : + silent persona switching (voice is a transport concern)
#   advance : + generated diagrams/charts/typed components (today's default)
#   extreme : + runtime whole-page generation & site API calls
# ---------------------------------------------------------------------------
_BASIC = (QUERY_CORTEX, NAVIGATE, SCROLL_TO)
_HIGH = _BASIC + (SET_PERSONA,)
_ADVANCE = _HIGH + (RENDER_COMPONENT, PATCH_COMPONENT)


def tools_for(level: str, site_key: str | None = None) -> list[ToolSpec]:
    """Return the tool subset allowed at an intelligence ``level``.

    ``site_key`` lets the extreme tier offer ``call_site_api`` only when the site
    actually has ingested APIs.
    """
    if level == "basic":
        return list(_BASIC)
    if level == "high":
        return list(_HIGH)
    if level == "extreme":
        extra: list[ToolSpec] = [GENERATE_PAGE]
        if site_key:
            # Local import avoids a config/registry import cycle at module load.
            from app.apis.registry import get_site_apis
            if get_site_apis(site_key).operations():
                extra.append(CALL_SITE_API)
        return list(_ADVANCE) + extra
    return list(_ADVANCE)  # advance (default)
