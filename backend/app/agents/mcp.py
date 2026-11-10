"""
The site's MCP server (Model Context Protocol, streamable HTTP) — M3-2.

``POST /mcp/{widget key}`` takes one JSON-RPC 2.0 message and answers with
JSON (no server-initiated streams, so ``GET`` is 405). Stateless: there is no
session to keep, which suits many replicas; ``initialize`` is still answered
so every client's handshake works.

Methods: ``initialize``, ``ping``, ``tools/list``, ``tools/call``,
``resources/list``, ``resources/read``, ``resources/templates/list``,
``prompts/list``; notifications get 202 and no body.

Tools are the read tools for anyone with the site's key, plus
``capture_lead`` / ``action_*`` when the request carries a token with that
scope (``Authorization: Bearer fbat_…``). Resources are the site's key pages.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents import tools

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
LATEST = SUPPORTED_VERSIONS[0]

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603


@dataclass
class Context:
    rt: Any
    site: dict[str, Any]
    token: Optional[dict[str, Any]]
    client: Optional[str]
    pages: list[dict[str, Any]]
    # Filled by view tools (Phase 5) so the traffic log records the view and action.
    meta: dict[str, Any] = field(default_factory=dict)


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def error(id_: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err}


def _can(ctx: Context, scope: str) -> bool:
    return bool(ctx.token and scope in ctx.token["scopes"])


VIEW_TOOLS = [
    {"name": "list_views",
     "description": "The website's pages that have a view: what each is for and its path.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "get_view",
     "description": "A page of the website as people see it — its sections, data and the actions it offers "
                    "(with whether an agent may do each). Give a path, or a plan_id from an earlier view.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "A path on the site, like /pricing."},
         "plan_id": {"type": "string", "description": "A view id (pl_…)."}},
         "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
]

RUN_VIEW_ACTION = {
    "name": "run_view_action",
    "description": "Do one of a view's actions. Actions whose policy is 'confirm' answer a summary and a "
                   "confirm_code first: ask the person you act for to approve, then call again with the same "
                   "inputs and the confirm_code. Actions whose policy is 'never' must be done by a person on "
                   "the page.",
    "inputSchema": {"type": "object", "properties": {
        "plan_id": {"type": "string"}, "action": {"type": "string"},
        "inputs": {"type": "object"}, "confirm_code": {"type": "string"}},
        "required": ["plan_id", "action"], "additionalProperties": False},
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
}


def tool_list(ctx: Context) -> list[dict[str, Any]]:
    out = tools.read_tool_specs() + VIEW_TOOLS
    if _can(ctx, "leads"):
        out.append(tools.LEAD_TOOL)
    if _can(ctx, "actions"):
        out += tools.action_tool_specs(ctx.site["site_key"])
        out.append(RUN_VIEW_ACTION)
    return out


def _text_result(payload: dict[str, Any], text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "structuredContent": payload, "isError": is_error}


def _answer_text(out: dict[str, Any]) -> str:
    lines = [out.get("answer") or "(no answer)"]
    if out.get("sources"):
        lines += ["", "Sources:"] + [f"- {s.get('title') or s.get('route') or s.get('url')}"
                                     + (f" ({s['url']})" if s.get("url") else "") for s in out["sources"]]
    for pl in out.get("price_lists") or []:
        lines += ["", f"{pl['action']}:"] + [f"- {p['label']}: {p['amount']}" for p in pl["prices"]]
    return "\n".join(lines)


async def call_tool(ctx: Context, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """(MCP tool result, ok)."""
    if not isinstance(args, dict):
        raise RpcError(INVALID_PARAMS, "arguments must be an object")
    try:
        if name == "search_knowledge":
            out = await tools.ask(ctx.rt, ctx.site, str(args.get("question") or ""))
            return _text_result(out, _answer_text(out)), True
        if name == "get_page":
            out = await tools.get_page(ctx.rt, ctx.site, str(args.get("path") or ""))
            return _text_result(out, _answer_text(out)), True
        if name == "list_offerings":
            out = await tools.list_offerings(ctx.rt, ctx.site)
            return _text_result(out, _answer_text(out)), True
        if name in ("list_views", "get_view", "run_view_action"):
            return await _view_tool(ctx, name, args)
        if name == "capture_lead":
            if not _can(ctx, "leads"):
                raise tools.ToolError("This needs a token from the site's owner with the 'leads' scope.")
            out = await tools.capture_lead(ctx.site, args, ctx.client)
            return _text_result(out, "Thanks — the team has it and will follow up by email."), True
        if name.startswith("action_"):
            if not _can(ctx, "actions"):
                raise tools.ToolError("This needs a token from the site's owner with the 'actions' scope.")
            out = await tools.run_action(ctx.site, name, args, ctx.token["id"])
            ok = out.get("status") in ("done", "paid")
            text = (out.get("message") or ("Done." if ok else f"It didn't work: {out.get('error') or out.get('status')}"))
            if out.get("url"):
                text += f"\n{out['url']}"
            return _text_result(out, text, is_error=not ok), ok
    except tools.ToolError as exc:
        return _text_result({"error": str(exc)}, str(exc), is_error=True), False
    raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")


async def _view_tool(ctx: Context, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    from app.agents import views

    if name == "list_views":
        out = await views.list_views(ctx.site)
        text = "\n".join(f"- {v['path']} — {v['title']}" + (f": {v['purpose']}" if v.get("purpose") else "")
                         for v in out["views"]) or "No pages have views yet."
        return _text_result(out, text), True
    if name == "get_view":
        view = await views.load_view(ctx.rt, ctx.site, path=args.get("path"), plan_id=args.get("plan_id"),
                                     html=True)
        if view is None:
            raise tools.ToolError("No view for that path or id.")
        ctx.meta["plan_id"] = view["plan_id"]
        html = view.pop("_html", "")
        result = _text_result(view, views.markdown(view))
        if html:  # for assistants that render UI in the chat (export seam, D3)
            result["content"].append({"type": "resource", "resource": {
                "uri": f"ui://fluidbuddha/view/{view['plan_id']}", "mimeType": "text/html", "text": html}})
        return result, True
    # run_view_action
    pid, action = str(args.get("plan_id") or ""), str(args.get("action") or "")
    ctx.meta.update(plan_id=pid, action=action)
    if not _can(ctx, "actions"):
        raise tools.ToolError("This needs a token from the site's owner with the 'actions' scope.")
    out = await views.run(ctx.rt, ctx.site, pid, action, args.get("inputs") or {}, ctx.token,
                          str(args.get("confirm_code") or ""))
    ctx.meta["status"] = out["status"]
    text = {"needs_confirmation": f"Needs approval: {out.get('summary')}. {out.get('message')} "
                                  f"confirm_code: {out.get('confirm_code')}",
            "done": "Done."}.get(out["status"], out.get("message") or f"It didn't work ({out['status']}).")
    return _text_result(out, text, is_error=out["status"] in ("refused", "failed")), \
        out["status"] in ("done", "needs_confirmation")


def resource_list(ctx: Context) -> list[dict[str, Any]]:
    return [{"uri": p["uri"], "name": p["name"], "mimeType": "text/plain",
             "description": f"What {p['name']} says, from {ctx.site['name']}'s content."} for p in ctx.pages]


async def handle(ctx: Context, msg: Any) -> tuple[Optional[dict[str, Any]], Optional[str], bool]:
    """One JSON-RPC message → (response or None for a notification, the tool
    or method it was, whether it worked)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return error(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST,
                     "Expected a JSON-RPC 2.0 request"), None, False
    method = msg["method"]
    id_ = msg.get("id")
    params = msg.get("params") or {}
    if "id" not in msg:                       # a notification: nothing to answer
        return None, method, True
    try:
        if method == "initialize":
            asked = params.get("protocolVersion")
            version = asked if asked in SUPPORTED_VERSIONS else LATEST
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False},
                                 "prompts": {"listChanged": False}},
                "serverInfo": {"name": f"{ctx.site['name']} (FluidBuddha)", "version": "1.0.0"},
                "instructions": (f"Answers about {ctx.site['name']} from its own content, with sources. "
                                 "Use search_knowledge for questions, list_offerings for plans and prices, "
                                 "list_views / get_view to see a page as people see it and what it offers."),
            }
            return {"jsonrpc": "2.0", "id": id_, "result": result}, method, True
        if method == "ping":
            return {"jsonrpc": "2.0", "id": id_, "result": {}}, method, True
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": id_, "result": {"tools": tool_list(ctx)}}, method, True
        if method == "tools/call":
            name = str(params.get("name") or "")
            result, ok = await call_tool(ctx, name, params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": id_, "result": result}, name, ok
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": id_, "result": {"resources": resource_list(ctx)}}, method, True
        if method == "resources/templates/list":
            return {"jsonrpc": "2.0", "id": id_, "result": {"resourceTemplates": []}}, method, True
        if method == "prompts/list":
            return {"jsonrpc": "2.0", "id": id_, "result": {"prompts": []}}, method, True
        if method == "resources/read":
            uri = str(params.get("uri") or "")
            page = next((p for p in ctx.pages if p["uri"] == uri), None)
            if page is None:
                raise RpcError(-32002, "Resource not found", {"uri": uri})
            out = await tools.get_page(ctx.rt, ctx.site, page["path"])
            return {"jsonrpc": "2.0", "id": id_, "result": {"contents": [
                {"uri": uri, "mimeType": "text/plain", "text": _answer_text(out)}]}}, "resources/read", True
        raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
    except RpcError as exc:
        return error(id_, exc.code, exc.message, exc.data), method, False
    except Exception as exc:
        logger.exception("mcp %s failed for %s", method, ctx.site["site_key"])
        return error(id_, INTERNAL, "Something went wrong answering that."), method, False


def parse(body: bytes) -> Any:
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise RpcError(PARSE_ERROR, "Parse error")
