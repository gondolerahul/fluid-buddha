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
        "has no authored pages) as an Experience Plan: ordered regions, each one "
        "component from the PAGE COMPONENTS list with its props. Write short copy "
        "grounded in `query_cortex` results; for live data (prices, plans, "
        "records) BIND a prop to a read operation instead of writing values: "
        "{\"bind\": \"api:<operationId>\", \"path\": \"$.items[*]\"}. Visual "
        "styling comes from the brand design system automatically."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "regions": {
                "type": "array",
                "description": "Ordered regions; each {id?, component, props}. A "
                               "prop is a literal or a binding {bind, path?, "
                               "params?, transform?}. See PAGE COMPONENTS and "
                               "BINDABLE DATA in context.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "component": {"type": "string"},
                        "props": {"type": "object"},
                    },
                    "required": ["component"],
                },
            },
            "actions": {
                "type": "array",
                "description": "Optional actions the page offers; each {id, ref: "
                               "'action:<name>' | 'api:<operationId>', confirm?}. "
                               "A prop 'action' refers to one by id.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "ref": {"type": "string"},
                        "confirm": {"type": "string", "enum": ["none", "card", "typed"]},
                    },
                    "required": ["id", "ref"],
                },
            },
            "sections": {
                "type": "array",
                "description": "Legacy form: ordered {type, props} sections of the "
                               "built-in types. Prefer `regions`.",
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
        "required": ["title"],
    },
)

PATCH_PLAN = ToolSpec(
    name="patch_plan",
    description=(
        "Edit the composed page that is ON SCREEN instead of building a new one: add, "
        "replace, remove or move regions by id. Use the same components, props and "
        "bindings rules as generate_page."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["add", "replace", "remove", "move"]},
                        "region": {"type": "string"},
                        "component": {"type": "string"},
                        "props": {"type": "object"},
                        "before": {"type": "string"},
                        "animation": {"type": "string", "enum": ["fade", "highlight", "count_up"]},
                    },
                    "required": ["op", "region"],
                },
            },
        },
        "required": ["ops"],
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

CAPTURE_LEAD = ToolSpec(
    name="capture_lead",
    description=(
        "Save the visitor as a sales lead when they share an email address or ask "
        "to be contacted, booked or sent details. Pass exactly what they said; "
        "never invent or guess an email."
    ),
    parameters={
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "name": {"type": "string"},
            "company": {"type": "string"},
            "interest": {"type": "string",
                         "description": "What they want, in a few words."},
        },
        "required": ["email"],
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
#   basic   : text chat + redirect/scroll + lead capture
#   high    : + silent persona switching (voice is a transport concern)
#   advance : + generated diagrams/charts/typed components (today's default)
#   extreme : + runtime whole-page generation & site API calls
# ---------------------------------------------------------------------------
# Lead capture is the point of the agent, so every tier gets it.
_BASIC = (QUERY_CORTEX, NAVIGATE, SCROLL_TO, CAPTURE_LEAD)
_HIGH = _BASIC + (SET_PERSONA,)
_ADVANCE = _HIGH + (RENDER_COMPONENT, PATCH_COMPONENT)


def tools_for(level: str, site_key: str | None = None) -> list[ToolSpec]:
    """Return the tool subset allowed at an intelligence ``level``.

    ``site_key`` lets the extreme tier offer ``call_site_api`` only when the site
    actually has ingested APIs, adds the site's own components to
    ``render_component`` and its actions as tools (every tier, M2-8).
    """
    if level == "basic":
        return list(_BASIC) + action_tools(site_key)
    if level == "high":
        return _with_site_personas(_HIGH, site_key) + action_tools(site_key)
    tools = [_site_render(site_key) if t is RENDER_COMPONENT else t
             for t in _with_site_personas(_ADVANCE, site_key)]
    if level == "extreme":
        extra: list[ToolSpec] = [GENERATE_PAGE]
        if site_key:
            # Local import avoids a config/registry import cycle at module load.
            from app.apis.registry import get_site_apis
            if get_site_apis(site_key).operations():
                extra.append(CALL_SITE_API)
        return tools + extra + action_tools(site_key)
    return tools + action_tools(site_key)  # advance (default)


def action_tools(site_key: str | None) -> list[ToolSpec]:
    """One tool per enabled action of the site (M2-8)."""
    if not site_key:
        return []
    from app.actions.fields import rupees, tool_parameters
    from app.actions.store import actions_for
    out = []
    for a in actions_for(site_key):
        desc = f"{a.label}. {a.description}".strip()
        if a.kind == "payment_link":
            desc += " Plans (the amount comes from this list, you only pick the plan): " + "; ".join(
                f"{p['key']} = {p['label']} at {rupees(p['amount'])}" for p in a.config.get("prices", []))
        desc += (" Calling this only shows the visitor a confirmation card; nothing happens "
                 "until they press Confirm. Use it when the visitor asks for it or agrees to it.")
        out.append(ToolSpec(name=a.tool_name, description=desc, parameters=tool_parameters(a.fields)))
    return out


def _site_render(site_key: str | None) -> ToolSpec:
    """render_component with the site's own components added (M2-8)."""
    if not site_key:
        return RENDER_COMPONENT
    from app.orchestrator.custom_components import components_for, describe
    custom = components_for(site_key)
    if not custom:
        return RENDER_COMPONENT
    params = {**RENDER_COMPONENT.parameters, "properties": {
        **RENDER_COMPONENT.parameters["properties"],
        "component_type": {"type": "string", "enum": [
            *RENDER_COMPONENT.parameters["properties"]["component_type"]["enum"], *custom]}}}
    return ToolSpec(
        name=RENDER_COMPONENT.name,
        description=RENDER_COMPONENT.description + "\nThis site's own components (prefer one "
        "when it fits what the visitor asks):\n" + "\n".join(describe(c) for c in custom.values()),
        parameters=params)


def _with_site_personas(tools: list[ToolSpec], site_key: str | None) -> list[ToolSpec]:
    """Swap the generic ``set_persona`` for one whose enum is this site's personas,
    or drop it when the site defines none (the model can't pick a persona the site
    doesn't have). ``site_key=None`` means the HireBuddha default."""
    from app.orchestrator.personas import valid_personas  # avoid an import cycle

    slugs = valid_personas(site_key or "hirebuddha")
    out: list[ToolSpec] = []
    for tool in tools:
        if tool.name != SET_PERSONA.name:
            out.append(tool)
        elif slugs:
            out.append(ToolSpec(
                name=SET_PERSONA.name,
                description=SET_PERSONA.description,
                parameters={
                    "type": "object",
                    "properties": {"persona": {"type": "string", "enum": list(slugs)}},
                    "required": ["persona"],
                },
            ))
    return out
