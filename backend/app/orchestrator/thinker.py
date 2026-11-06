"""
Heavy Thinker (Req 3.3.2) — the grounded reasoning engine.

Runs the standard function-calling loop: the model must call ``query_cortex``
to ground itself, may then call client-action / component tools, and finishes
with the spoken explanation as plain text. ``query_cortex`` is executed
server-side; action/component tools are recorded, assigned a ``sync_id`` and
acked so the model can continue.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.ai.base import ChatMessage, LLMClient
from app.config import Settings
from app.cortex.bridge import CortexBridge
from app.cortex.query import citations, query_cortex
from app.orchestrator.components import normalize_component
from app.orchestrator.pagegen import build_extreme_brief
from app.orchestrator.personas import valid_personas
from app.orchestrator.profile import profile_for
from app.orchestrator.prompts import build_reaction_system, build_thinker_system
from app.orchestrator.result import (
    ClientAction,
    ComponentPatch,
    ComponentPayload,
    Grounding,
    PageSpec,
)
from app.orchestrator.sitemap import resolve_route
from app.orchestrator.tools import ACTION_TOOLS, COMPONENT_TOOLS, tools_for
from app.trust.pii import PiiVault

logger = logging.getLogger(__name__)

# Each loop iteration is a full LLM round-trip, so fewer = lower latency. Four
# is plenty for the common path (one grounding search, then act + speak) while
# still leaving headroom; the forced-answer pass below guarantees a reply.
_MAX_TURNS = 4
# Hard cap on real cortex searches per turn. One grounded retrieval (top_k=5)
# answers nearly every SDR question; a second search is a whole extra round-trip
# of latency for marginal gain, so we cap at one. Gemini 3.x keeps emitting
# query_cortex (copying the history pattern) even after we withdraw it from the
# tool list, so we ALSO refuse to execute it past this many calls.
_MAX_CORTEX = 1


def _sync_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _account(result: "ThinkResult", resp, system: str = "", messages=()) -> None:
    """Add one LLM call's token + tool-call spend to the result (req F). Falls
    back to a length estimate when the engine reports no usage (mock mode)."""
    from app.analytics.pricing import estimate_tokens
    in_tok = resp.input_tokens or (
        estimate_tokens(system) + sum(estimate_tokens(getattr(m, "text", "")) for m in messages)
    )
    out_tok = resp.output_tokens or estimate_tokens(resp.text)
    result.input_tokens += int(in_tok)
    result.output_tokens += int(out_tok)
    result.tool_calls += len(resp.tool_calls or [])


def _on_screen_block(on_screen: dict[str, dict]) -> str:
    """Tell the model which components are live so a correction can patch one
    in place (``patch_component``) instead of rendering a duplicate (D-11)."""
    import json
    lines = []
    for sid, entry in on_screen.items():
        state = json.dumps(entry.get("state", {}), default=str)
        if len(state) > 300:
            state = state[:300] + "…"
        lines.append(f"- sync_id {sid}: {entry.get('component_type', '')} state={state}")
    return (
        "\n\nON-SCREEN COMPONENTS (the visitor can see these now; to change one "
        "after a correction call patch_component with its sync_id and only the "
        "changed fields — do not re-render it):\n" + "\n".join(lines)
    )


@dataclass
class ThinkResult:
    answer_text: str = ""
    actions: list[ClientAction] = field(default_factory=list)
    components: list[ComponentPayload] = field(default_factory=list)
    pages: list[PageSpec] = field(default_factory=list)
    patches: list[ComponentPatch] = field(default_factory=list)
    plan_patches: list[Any] = field(default_factory=list)   # PlanPatch (P2-4)
    # Contact details the visitor shared (capture_lead); saved by the transport
    # once the turn is recorded, so the lead links to its conversation.
    leads: list[Any] = field(default_factory=list)
    # Actions proposed this turn (M2-8): (Action, checked inputs). Stored as
    # runs by the transport; nothing happens until the visitor confirms.
    proposals: list[Any] = field(default_factory=list)
    grounding: Grounding = field(default_factory=Grounding)
    # Cost analytics (req F): which LLM tier ran + the tokens/tool-calls it spent.
    llm_kind: str = "thinker"        # 'fast' (lean) | 'thinker' (heavy)
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0


class HeavyThinker:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings

    async def think(
        self,
        *,
        user_text: str,
        persona: Optional[str],
        bridge: CortexBridge,
        history: Sequence[ChatMessage] = (),
        site_key: str = "hirebuddha",
        intelligence: str = "advance",
        page: Optional[str] = None,
        section: Optional[str] = None,
        sections: Optional[list[dict]] = None,
        related: Optional[list] = None,
        probe: bool = False,
        on_screen: Optional[dict[str, dict]] = None,
        pii: Optional[PiiVault] = None,
        lang: str = "en",
        seen: str = "en",
        on_screen_plan: Optional[dict] = None,
        taste_brief: str = "",
    ) -> ThinkResult:
        extreme_brief = build_extreme_brief(site_key) if intelligence == "extreme" else None
        system = build_thinker_system(
            persona, site_key, intelligence=intelligence,
            page=page, section=section, sections=sections,
            extreme_brief=extreme_brief, related=related, probe=probe,
            lang=lang, seen=seen,
        )
        if taste_brief:  # the visitor's taste (Phase 3): shape, never facts
            system += ("\nVISITOR TASTE: " + taste_brief + " Shape the answer's length and "
                       "format to it; never change facts or prices for it.")
        gated_tools = tools_for(intelligence, site_key)
        on_screen = dict(on_screen or {})
        if on_screen and any(t.name == "patch_component" for t in gated_tools):
            system += _on_screen_block(on_screen)
        # A composed page is on screen (P2-4): offer edits to it.
        if on_screen_plan and intelligence == "extreme":
            from app.experience.patch import outline
            from app.orchestrator.tools import PATCH_PLAN

            gated_tools = [*gated_tools, PATCH_PLAN]
            system += "\n" + outline(on_screen_plan)
        messages: list[ChatMessage] = list(history) + [
            ChatMessage(role="user", text=user_text)
        ]
        result = ThinkResult()
        cortex_calls = 0
        t0 = time.monotonic()
        turns = 0

        # Tools are gated by the configured intelligence tier. The no-cortex
        # variant (offered once the search budget is spent) is derived from the
        # SAME gated set so a lower tier never gets a higher-tier tool back.
        no_cortex_tools = [t for t in gated_tools if t.name != "query_cortex"]

        for _ in range(_MAX_TURNS):
            turns += 1
            # After the search budget is spent, withdraw query_cortex from the
            # offered tools so the model is nudged to act/answer instead.
            tools = gated_tools if cortex_calls < _MAX_CORTEX else no_cortex_tools
            resp = await self._llm.generate(
                system=system,
                messages=messages,
                tools=tools,
                model=self._settings.heavy_model,
                temperature=0.5,
                max_output_tokens=1024,
                # Thinking disabled for latency: gemini-3.5-flash "thinking" adds
                # ~1s+/call (and several calls per turn) for little gain on this
                # grounded-SDR task. Raise this to re-enable deeper reasoning.
                thinking_budget=1,
            )
            _account(result, resp, system, messages)

            # Capture spoken text on EVERY turn: Gemini 3.x often bundles the
            # final answer in the same turn as its action tool calls (navigate/
            # render), so we must not wait for a tool-free turn to keep it.
            if resp.text.strip():
                result.answer_text = resp.text.strip()

            if not resp.tool_calls:
                break

            # Replay the model's tool-call turn (required for Vertex ordering).
            messages.append(ChatMessage(role="model", tool_calls=resp.tool_calls, raw=resp.raw))
            productive = False  # did this turn do anything other than over-budget search?
            for call in resp.tool_calls:
                over_budget = (
                    call.name == "query_cortex" and cortex_calls >= _MAX_CORTEX
                )
                if over_budget:
                    # Gemini re-calls query_cortex even after it's withdrawn (it
                    # copies the history pattern); refuse the extra search rather
                    # than execute it, and tell it to answer now.
                    tool_result: Any = {
                        "ok": False,
                        "note": "Search budget reached — answer now using prior "
                                "results; do not search again.",
                    }
                else:
                    if call.name == "query_cortex":
                        cortex_calls += 1
                    tool_result = await self._handle_tool_call(
                        call, bridge, result, site_key, on_screen, pii,
                        page_ctx={"persona": persona, "page": page, "lang": lang},
                        on_screen_plan=on_screen_plan,
                    )
                    if call.name == "patch_plan" and result.plan_patches:
                        on_screen_plan = result.plan_patches[-1].plan
                    productive = True
                messages.append(ChatMessage(
                    role="tool", tool_name=call.name, tool_result=tool_result
                ))

            # A whole turn of nothing-but-refused-searches → stop; the finishing
            # pass below will force a spoken answer from what we already have.
            if not productive:
                logger.info("thinker: search budget exhausted, forcing answer")
                break
        else:
            logger.warning("Heavy Thinker hit max turns without a final answer")

        # If the model kept calling tools and never spoke, force a final answer.
        # A tool-free pass alone returns empty under the strict "must ground"
        # system prompt, so we add an explicit nudge to answer from context.
        if not result.answer_text:
            nudge = ChatMessage(
                role="user",
                text="Now answer me directly in 2-3 spoken sentences using what "
                     "you found. Do not call any tools.",
            )
            forced = await self._llm.generate(
                system=system,
                messages=list(messages) + [nudge],
                model=self._settings.heavy_model,
                temperature=0.5,
                max_output_tokens=512,
                thinking_budget=0,  # no thinking — spend the whole budget on the answer
            )
            _account(result, forced, system, list(messages) + [nudge])
            if forced.text.strip():
                result.answer_text = forced.text.strip()

        if not result.answer_text:
            result.answer_text = (
                "Here's what I found — want me to go deeper on any part?"
                if result.grounding.found
                else "I want to get this exactly right — let me connect you with the team."
            )

        logger.info(
            "thinker done in %.1fs: turns=%d cortex_searches=%d actions=%d "
            "components=%d grounded=%s answer_len=%d",
            time.monotonic() - t0, turns, cortex_calls, len(result.actions),
            len(result.components), result.grounding.found, len(result.answer_text),
        )
        return result

    @staticmethod
    def _page_ctx(site_key: str, page_ctx: Optional[dict[str, Any]]) -> dict[str, Any]:
        """Request context a page binding may read (``ctx.<name>``)."""
        ctx = {k: v for k, v in (page_ctx or {}).items() if v}
        ctx["site_key"] = site_key
        ctx["currency"] = profile_for(site_key).currency
        return ctx

    async def _patch_plan(self, args: dict, site_key: str, bridge: CortexBridge, result: "ThinkResult",
                          plan: Optional[dict], ctx: dict[str, Any]) -> dict:
        """P2-4: apply ops to the page on screen; bind what changed."""
        if not plan:
            return {"ok": False, "error": "no composed page is on screen"}
        from app.apis.registry import get_site_apis
        from app.db import session_scope
        from app.experience.binding import bind_plan
        from app.experience.manifest import load_manifest
        from app.experience.patch import apply_ops
        from app.experience.plan import validate_plan
        from app.experience.resolvers import make_resolver
        from app.orchestrator.result import PlanPatch

        raw, accepted, problems = apply_ops(plan, args.get("ops"))
        manifest, registry = load_manifest(site_key), get_site_apis(site_key)
        report = validate_plan(raw, manifest=manifest, catalogue=registry, site_key=site_key)
        report.plan.plan_id = plan.get("plan_id") or report.plan.plan_id
        problems += report.problems + report.dropped
        kept = {r.id for r in report.plan.regions}
        changed = {o["region"] for o in accepted if o["op"] in ("add", "replace")}
        async with session_scope() as db:
            bound = await bind_plan(report.plan, manifest=manifest, registry=registry, ctx=ctx,
                                    resolve=make_resolver(db, None, site_key, bridge=bridge))
        sections = {b.id: b.to_section() for b in bound if b.id in changed and b.state == "ready"}
        ops = []
        for o in accepted:
            if o["op"] in ("add", "replace"):
                if o["region"] not in sections:
                    problems.append(f"{o['op']} {o['region']}: dropped (invalid or no data)")
                    continue
                ops.append({**o, "section": sections[o["region"]]})
            elif o["op"] == "remove" or o["region"] in kept:
                ops.append(o)
        if not ops:
            return {"ok": False, "problems": problems[:12] or ["nothing to change"]}
        new_plan = report.plan.to_dict()
        result.plan_patches.append(PlanPatch(plan_id=new_plan["plan_id"], ops=ops, plan=new_plan))
        out: dict[str, Any] = {"ok": True, "plan_id": new_plan["plan_id"],
                               "applied": [f"{o['op']} {o['region']}" for o in ops]}
        if problems:
            out["problems"] = problems[:12]
        return out

    async def _handle_tool_call(
        self, call, bridge: CortexBridge, result: ThinkResult, site_key: str,
        on_screen: Optional[dict[str, dict]] = None,
        pii: Optional[PiiVault] = None,
        page_ctx: Optional[dict[str, Any]] = None,
        on_screen_plan: Optional[dict] = None,
    ):
        name = call.name
        args = call.args or {}

        if name == "query_cortex":
            res = await query_cortex(
                bridge,
                args.get("query", ""),
                top_k=self._settings.cortex_retrieval_top_k,
                threshold=self._settings.cortex_confidence_threshold,
            )
            result.grounding = Grounding(
                confidence=res["confidence"],
                found=res["found"],
                sources=citations(res.get("snippets", [])),
            )
            return res

        if name == "generate_page":
            # Experience Plan pipeline (P0-5): validate → bind → render. The
            # model gets ids and problems back, never the bound data.
            from app.experience.compose import compose_page

            page, tool_result = await compose_page(
                args, site_key=site_key, sync_id=_sync_id("page"),
                ctx=self._page_ctx(site_key, page_ctx), bridge=bridge,
            )
            if page.sections:
                result.pages.append(page)
            return tool_result

        if name == "patch_plan":
            return await self._patch_plan(args, site_key, bridge, result, on_screen_plan,
                                          self._page_ctx(site_key, page_ctx))

        if name == "call_site_api":
            from app.apis.registry import get_site_apis
            return await get_site_apis(site_key).call(
                args.get("operation_id", ""), args.get("params") or {}
            )

        if name in COMPONENT_TOOLS:
            if name == "render_component":
                sync_id = _sync_id("ui")
                try:
                    ctype, st = normalize_component(
                        args.get("component_type", "table"), args.get("initial_state", {}) or {},
                        site_key=site_key,
                    )
                except ValueError as exc:   # a custom component's props didn't fit
                    return {"ok": False, "error": str(exc),
                            "hint": "Pass initial_state matching the component's props."}
                result.components.append(ComponentPayload(
                    sync_id=sync_id,
                    component_type=ctype,
                    initial_state=st,
                    explanation_text=args.get("explanation_text", "") or "",
                ))
                return {"ok": True, "sync_id": sync_id}
            # patch_component — only a component the visitor can see right now.
            target = str(args.get("target_sync_id") or "")
            patch = args.get("patch")
            if target not in (on_screen or {}):
                return {"ok": False, "error": "unknown_sync_id",
                        "hint": "Patch only a sync_id listed under ON-SCREEN "
                                "COMPONENTS, or render a new component."}
            if not isinstance(patch, dict) or not patch:
                return {"ok": False, "error": "empty_patch"}
            animation = args.get("animation")
            result.patches.append(ComponentPatch(
                target_sync_id=target, patch=patch,
                animation=animation if animation in ("fade", "count_up", "highlight") else None,
            ))
            return {"ok": True, "target_sync_id": target}

        if name in ACTION_TOOLS:
            action = self._to_action(name, args, site_key)
            if action:
                result.actions.append(action)
                return {"ok": True}
            if name == "navigate":
                # Bad/unknown path — tell the model so it can correct or just speak.
                return {
                    "ok": False,
                    "error": "invalid_route",
                    "hint": "That path is not a real page. Use only a route from "
                            "VALID ROUTES, or answer without navigating.",
                }
            return {"ok": True}

        if name.startswith("action_"):
            from app.actions.fields import InputError, validate_inputs
            from app.actions.store import actions_for
            action = next((a for a in actions_for(site_key) if a.tool_name == name), None)
            if action is None:
                return {"ok": False, "error": "unknown action"}
            if any(p[0].name == action.name for p in result.proposals):
                return {"ok": False, "error": "already proposed this turn"}
            # The model saw placeholders; the action gets what the visitor typed.
            if pii is not None:
                args = pii.unmask_args(args)
            try:
                inputs = validate_inputs(action.fields, args)
            except InputError as exc:
                return {"ok": False, "error": str(exc),
                        "hint": "Ask the visitor for what's missing, then call it again."}
            result.proposals.append((action, inputs))
            return {"ok": True, "status": "waiting_for_the_visitor",
                    "note": "Nothing has happened yet. Tell the visitor to check the details "
                            "on screen and press Confirm; never say it is done."}

        if name == "capture_lead":
            from app.leads.store import LeadError, LeadIn
            # The model saw placeholders; the lead gets what the visitor typed.
            if pii is not None:
                args = pii.unmask_args(args)
            try:
                lead = LeadIn(email=args.get("email") or "", name=args.get("name"),
                              company=args.get("company"),
                              interest=args.get("interest")).cleaned()
            except LeadError as exc:
                return {"ok": False, "error": str(exc),
                        "hint": "Ask the visitor for a valid email address."}
            result.leads.append(lead)
            return {"ok": True, "note": "Saved. Tell them someone will follow up."}

        logger.warning("Unknown tool call: %s", name)
        return {"ok": False, "error": "unknown tool"}

    def _to_action(
        self, name: str, args: dict, site_key: str
    ) -> Optional[ClientAction]:
        if name == "navigate":
            # Snap the model's guess to a real route; drop it if too far off so
            # the visitor is never sent to a 404 (Req 3.5).
            path = resolve_route(site_key, args.get("path") or "")
            if not path:
                logger.warning("navigate dropped — invalid path %r", args.get("path"))
                return None
            return ClientAction(type="navigate", path=path)
        if name == "scroll_to":
            section_id = args.get("section_id")
            direction = args.get("direction")
            if not section_id and not direction:
                return None
            return ClientAction(
                type="scroll_to", section_id=section_id, direction=direction
            )
        if name == "set_persona":
            persona = args.get("persona")
            if persona in valid_personas(site_key):
                return ClientAction(type="set_icp", icp=persona)
        return None

    async def react(
        self, *, component_type: str, state: dict,
        persona: Optional[str] = None, site_key: str = "hirebuddha", lang: str = "en",
    ) -> str:
        """A short, live spoken reaction to the visitor interacting with a
        component. Ungrounded by design (it comments on the numbers they're
        exploring), so it uses the fast model and no tools."""
        system = build_reaction_system(persona, site_key, component_type, state, lang)
        try:
            resp = await self._llm.generate(
                system=system,
                messages=[ChatMessage(
                    role="user",
                    text="React in one short spoken sentence to my latest change.",
                )],
                model=self._settings.fast_model,
                temperature=0.6,
                max_output_tokens=80,
                thinking_budget=0,
            )
        except Exception as exc:
            logger.warning("react failed: %s", exc)
            return ""
        return resp.text.strip()

    async def welcome(
        self,
        *,
        persona: Optional[str],
        bridge: CortexBridge,
        site_key: str = "hirebuddha",
        intelligence: str = "advance",
        page: Optional[str] = None,
        section: Optional[str] = None,
        sections: Optional[list[dict]] = None,
        lang: str = "en",
    ) -> ThinkResult:
        """Agent-initiated greeting that introduces the current page (Req 3.x,
        voice-first onboarding). Grounded via the same query_cortex loop."""
        directive = (
            "The visitor just arrived"
            + (f" on {page}" if page else "")
            + f". Greet them warmly by name as {profile_for(site_key).agent_name} "
            "in ONE or TWO short sentences, "
            "briefly say what this page is about (ground it with query_cortex), and "
            "invite them to ask a question or have you show them around. Do not "
            "navigate or render components yet."
        )
        return await self.think(
            user_text=directive,
            persona=persona,
            bridge=bridge,
            history=(),
            site_key=site_key,
            intelligence=intelligence,
            page=page,
            section=section,
            sections=sections,
            lang=lang,
            seen=lang,
        )
