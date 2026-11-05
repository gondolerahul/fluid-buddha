"""
What an AI assistant can do through the site's agent endpoint (M3-2).

Reading (the site's public widget key is enough):

* ``search_knowledge`` — a grounded answer from the site's knowledge, with
  its sources: the same agent and guardrails as the widget (citations, pinned
  and blocked answers, medical safety), one stateless turn;
* ``get_page`` — what one page of the site says (a grounded summary);
* ``list_offerings`` — plans and prices, from the knowledge and the site's
  payment price lists.

Doing (a token the customer issued, with the matching scope):

* ``capture_lead`` (scope ``leads``) — a lead, delivered like any other;
* ``action_<name>`` (scope ``actions``) — the site's enabled actions (payment
  link, quote, trial, meeting, webhook) with their typed inputs. The token is
  the customer's authorisation, so the action runs at once; amounts still
  come only from the configured price list.
"""
from __future__ import annotations

import logging
import uuid
import time
from typing import Any, Optional

from app.actions import fields as action_fields
from app.actions import run as action_runner
from app.actions import store as actions

logger = logging.getLogger(__name__)

READ_TOOLS = ("search_knowledge", "get_page", "list_offerings")


class ToolError(Exception):
    """Shown to the assistant as a tool error (not a protocol error)."""


def read_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": "search_knowledge",
         "description": "Ask the website's own agent a question about the company, its products, "
                        "pricing or policies. Answers only from the site's content, with sources.",
         "inputSchema": {"type": "object", "properties": {
             "question": {"type": "string", "description": "The question, in English or Hindi."}},
             "required": ["question"], "additionalProperties": False},
         "annotations": {"readOnlyHint": True, "openWorldHint": False}},
        {"name": "get_page",
         "description": "What a page of the website says, summarised from the site's content.",
         "inputSchema": {"type": "object", "properties": {
             "path": {"type": "string", "description": "A path on the site, like /pricing."}},
             "required": ["path"], "additionalProperties": False},
         "annotations": {"readOnlyHint": True, "openWorldHint": False}},
        {"name": "list_offerings",
         "description": "The company's plans, products and prices.",
         "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
         "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    ]


LEAD_TOOL = {
    "name": "capture_lead",
    "description": "Pass a person's interest to the company's team (they'll follow up by email).",
    "inputSchema": {"type": "object", "properties": {
        "email": {"type": "string"}, "name": {"type": "string"}, "company": {"type": "string"},
        "message": {"type": "string", "description": "What they're interested in."}},
        "required": ["email"], "additionalProperties": False},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
}


def action_tool_specs(site_key: str) -> list[dict[str, Any]]:
    out = []
    for a in actions.actions_for(site_key):
        out.append({"name": a.tool_name, "description": a.description or a.label,
                    "inputSchema": action_fields.tool_parameters(a.fields),
                    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}})
    return out


async def ask(rt: Any, site: dict[str, Any], question: str) -> dict[str, Any]:
    """One stateless, grounded turn of the site's agent."""
    from app.ai.providers import current_site
    from app.analytics.usage import TurnMetrics, record_turn
    from app.db import session_scope
    from app.design.system import ensure_design
    from app.orchestrator.profile import ensure_profile, profile_for
    from app.orchestrator.state import ConversationState
    from app.routes.actions import ensure_extras
    from app.trust.settings import get_privacy

    question = " ".join((question or "").split())[:1000]
    if not question:
        raise ToolError("Ask a question.")
    site_key = site["site_key"]
    t0 = time.monotonic()
    await ensure_profile(site_key)
    await ensure_design(site_key)
    await ensure_extras(site_key)
    current_site.set(site_key)
    # Read-only: answer at the "advance" tier at most, never acting on a page.
    state = ConversationState(site_key=site_key, intelligence="advance" if site["intelligence"] != "basic" else "basic")
    async with session_scope() as db:
        privacy = await get_privacy(db, site_key)
    state.pii.enabled = privacy.redact_pii
    masked = state.pii.mask(question)
    state.pick_language(masked, profile_for(site_key).languages)

    if profile_for(site_key).safety == "medical":
        from app.trust.safety import check, reply
        verdict = check(masked)
        if verdict:
            return {"answer": reply(verdict, state.lang), "sources": [], "found": True}

    async with session_scope() as db:
        bridge = rt.bridge(db, site_key=site_key)
        result = await rt.loop.run_turn(user_text=masked, state=state, bridge=bridge)
    try:
        async with session_scope() as adb:
            m = TurnMetrics(site_key=site_key, session_id=None, channel="agent", intent=result.intent,
                            latency_ms=(time.monotonic() - t0) * 1000.0)
            m.add_llm(kind=result.llm_kind, input_tokens=result.input_tokens,
                      output_tokens=result.output_tokens, tool_calls=result.tool_calls)
            await record_turn(adb, m)
    except Exception as exc:
        logger.debug("agent usage record skipped: %s", exc)
    sources = [d for d in ({k: s.get(k) for k in ("title", "url", "route") if s.get(k)}
                           for s in (result.grounding.sources or []) if isinstance(s, dict)) if d][:6]
    return {"answer": state.pii.spoken(result.answer_text or result.ack or ""),
            "sources": sources, "found": bool(result.grounding.found)}


async def get_page(rt: Any, site: dict[str, Any], path: str) -> dict[str, Any]:
    path = "/" + (path or "").strip().lstrip("/")
    if len(path) > 200 or any(c in path for c in "\n\r\t "):
        raise ToolError("A path on the site, like /pricing.")
    out = await ask(rt, site, f"Summarise what the page {path} of this website says.")
    url = f"https://{site['domain']}{path}" if site.get("domain") else None
    return {"path": path, "url": url, **out}


async def list_offerings(rt: Any, site: dict[str, Any]) -> dict[str, Any]:
    out = await ask(rt, site, "What plans, products or packages do you offer, and what do they cost?")
    price_lists = []
    for a in actions.actions_for(site["site_key"]):
        if a.kind == "payment_link":
            price_lists.append({"action": a.label, "prices": [
                {"plan": p["key"], "label": p["label"], "amount": action_fields.rupees(p["amount"])}
                for p in a.config.get("prices") or []]})
    return {**out, "price_lists": price_lists}


async def capture_lead(site: dict[str, Any], args: dict[str, Any], client: Optional[str]) -> dict[str, Any]:
    from app.db import session_scope
    from app.leads import delivery
    from app.leads import store as leads

    try:
        lead_in = leads.LeadIn(email=str(args.get("email") or ""), name=args.get("name"),
                               company=args.get("company"), message=args.get("message"),
                               interest=f"Sent by an AI assistant ({client or 'unknown'})")
        async with session_scope() as db:
            lead = await leads.create_lead(db, site_key=site["site_key"], lead=lead_in, source="agent")
            await db.commit()
    except leads.LeadError as exc:
        raise ToolError(str(exc))
    await delivery.deliver_lead(lead)
    return {"ok": True, "lead_id": lead["id"]}


async def run_action(site: dict[str, Any], tool: str, args: dict[str, Any], token_id: Any) -> dict[str, Any]:
    from app.db import session_scope
    from app.routes.actions import visitor_view

    action = next((a for a in actions.actions_for(site["site_key"]) if a.tool_name == tool), None)
    if action is None:
        raise ToolError("No such action.")
    session = f"agent:{token_id}"
    try:
        async with session_scope() as db:
            run = await actions.propose(db, action, session, args or {})
            await db.commit()
            done = await action_runner.confirm(db, site["site_key"], session, uuid.UUID(run["id"]))
    except action_fields.InputError as exc:
        raise ToolError(str(exc))
    except (PermissionError, LookupError) as exc:
        raise ToolError(str(exc))
    return visitor_view(done)
