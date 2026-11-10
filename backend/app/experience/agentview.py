"""
Agent-ready views (generative experience Phase 5, strategy §6).

The plan is the contract: the same plan a human sees is served to agents as

* a **view** — structured data (``fb.view/1``): regions in order with stable ids and
  their bound values, the plan's actions with their agent policy, JSON-LD and links;
* **text** — a markdown rendering of the same view;
* **tools** — the plan's actions, callable under the owner's confirmation rules.

Same facts as the page (no cloaking): only the presentation changes.

Agent policy per action (``auto`` | ``confirm`` | ``never``):

* from the plan action's confirm level — none → auto, card → confirm, typed → never
  (a human types it on the page);
* the API's ``x-fb-agent`` annotation can tighten or relax it, but ``never`` wins and
  destructive operations are never for agents.

``confirm`` is a two-step call: the first answers a summary and a one-time code; the
agent gets its human's approval and calls again with the code (same inputs, within
10 minutes, once).
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SCHEMA = "fb.view/1"
POLICIES = ("auto", "confirm", "never")
CONFIRM_TTL_S = 600

# AI agents and assistants that fetch pages for a person or for answers. Kept
# separate from generic bots: agents get the plain rendering as well.
_AGENT_UA = re.compile(
    r"gptbot|chatgpt-user|oai-searchbot|claudebot|claude-user|claude-searchbot|claude-web|anthropic-ai|"
    r"perplexitybot|perplexity-user|google-extended|googleother|applebot-extended|meta-externalagent|"
    r"meta-externalfetcher|amazonbot|bytespider|cohere-ai|mistralai-user|duckassistbot|youbot|"
    r"ai2bot|diffbot|timpibot",
    re.IGNORECASE,
)


def detect_agent(user_agent: Optional[str], headers: Any = None, query: Optional[dict[str, str]] = None
                 ) -> Optional[str]:
    """The agent's name when the caller is an AI agent, else None.

    Signals: a known agent user agent, a Web Bot Auth ``Signature-Agent`` header
    (signed agent identity), or ``?fbmode=agent``."""
    if query and query.get("fbmode") == "agent":
        return "declared"
    sig = headers.get("signature-agent") if headers is not None else None
    if sig:
        return str(sig).strip('"')[:80] or "signed agent"
    m = _AGENT_UA.search(user_agent or "")
    return m.group(0) if m else None


# ---- actions and policies -----------------------------------------------------------------

def _label_for(action_id: str, sections: list[dict[str, Any]]) -> str:
    for s in sections:
        p = s.get("props") or {}
        if p.get("action") == action_id and isinstance(p.get("cta_label"), str):
            return p["cta_label"]
    return action_id.replace("_", " ").capitalize()


def agent_policy(confirm: str, op: Any = None) -> str:
    """The policy for agent callers (see the module docstring)."""
    base = {"none": "auto", "card": "confirm", "typed": "never"}.get(confirm, "confirm")
    if op is None:
        return base
    if getattr(op, "effect", "") == "destructive":
        return "never"
    declared = getattr(op, "agent", "") or ""
    if declared == "never" or base == "never":
        return "never"
    return declared or base


def describe_actions(plan: dict[str, Any], sections: list[dict[str, Any]], site_key: str) -> list[dict[str, Any]]:
    """The plan's actions as agent tools: id, label, kind, policy, inputs."""
    from app.actions import fields as action_fields
    from app.actions import store as site_actions
    from app.apis.registry import get_site_apis

    registry = get_site_apis(site_key)
    by_name = {a.name: a for a in site_actions.actions_for(site_key)}
    out = []
    for a in plan.get("actions") or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        ref, confirm = str(a.get("ref") or ""), str(a.get("confirm") or "card")
        d: dict[str, Any] = {"id": a["id"], "label": _label_for(a["id"], sections), "ref": ref}
        if ref.startswith("action:"):
            sa = by_name.get(ref[7:])
            if sa is None or not sa.enabled:
                continue
            d.update(kind="site_action", description=sa.description or sa.label,
                     inputs=action_fields.tool_parameters(sa.fields), policy=agent_policy(confirm))
        elif ref.startswith("api:"):
            op = registry.operation(ref[4:])
            if op is None:
                continue
            d.update(kind="api", description=op.summary or ref[4:],
                     inputs=op.input_schema or {"type": "object", "properties": {}},
                     policy=agent_policy(confirm, op))
        else:
            continue
        out.append(d)
    return out


# ---- semantic layer ---------------------------------------------------------------------

_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)")


def _price(value: Any) -> Optional[str]:
    m = _NUM.search(str(value or ""))
    return m.group(1).replace(",", "") if m else None


def json_ld(sections: list[dict[str, Any]], *, title: str, description: str, url: str,
            org: str = "", currency: str = "") -> dict[str, Any]:
    """schema.org JSON-LD for a view, from its bound regions only."""
    page: dict[str, Any] = {"@type": "WebPage", "name": title, "description": description, "url": url}
    graph: list[dict[str, Any]] = [page]
    if org:
        o: dict[str, Any] = {"@type": "Organization", "name": org}
        if url.startswith("https://"):
            o["url"] = "/".join(url.split("/")[:3])
        graph.append(o)
    for s in sections:
        t, p = s.get("type"), s.get("props") or {}
        if t == "faq":
            qs = [{"@type": "Question", "name": str(i.get("q")),
                   "acceptedAnswer": {"@type": "Answer", "text": str(i.get("a"))}}
                  for i in p.get("items") or [] if isinstance(i, dict) and i.get("q") and i.get("a")]
            if qs:
                graph.append({"@type": "FAQPage", "mainEntity": qs})
        elif t == "pricing_table":
            offers = []
            for i in p.get("tiers") or []:
                if not isinstance(i, dict) or not i.get("name"):
                    continue
                offer: dict[str, Any] = {"@type": "Offer", "name": str(i["name"])}
                amount = _price(i.get("price"))
                if amount:
                    offer["price"] = amount
                    if currency:
                        offer["priceCurrency"] = currency
                feats = [str(f) for f in i.get("features") or [] if isinstance(f, (str, int, float))]
                if feats:
                    offer["description"] = "; ".join(feats)[:300]
                offers.append(offer)
            if offers:
                graph.append({"@type": "OfferCatalog", "name": str(p.get("title") or "Plans"),
                              "itemListElement": offers})
    if len(graph) == 1:
        return {"@context": "https://schema.org", **page}
    return {"@context": "https://schema.org", "@graph": graph}


def _md_items(items: Any) -> list[dict[str, Any]]:
    return [i for i in (items or []) if isinstance(i, dict)][:40]


def _cell(v: Any) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def section_markdown(s: dict[str, Any]) -> str:
    t, p = str(s.get("type") or ""), s.get("props") or {}
    act = f" (action `{p['action']}`)" if p.get("action") else ""
    head = (lambda lvl: f"{'#' * lvl} {p['title']}\n\n" if p.get("title") else "")
    if t == "hero":
        out = f"# {p.get('title') or ''}\n\n" + (f"{p['subtitle']}\n\n" if p.get("subtitle") else "")
        return out + (f"[{p['cta_label']}]{act}\n" if p.get("cta_label") else "")
    if t in ("text", "cta"):
        out = head(2) + (f"{p['body']}\n\n" if p.get("body") else "")
        return out + (f"[{p['cta_label']}]{act}\n" if p.get("cta_label") else "")
    if t == "feature_grid":
        return head(2) + "".join(f"- **{i.get('title') or ''}** — {i.get('body') or ''}\n" for i in _md_items(p.get("items")))
    if t == "pricing_table":
        out = head(2)
        for i in _md_items(p.get("tiers")):
            out += f"### {i.get('name') or ''}" + (f" — {i['price']}" if i.get("price") else "") + "\n\n"
            out += "".join(f"- {f}\n" for f in i.get("features") or [] if isinstance(f, (str, int, float))) + "\n"
        return out
    if t == "faq":
        return head(2) + "".join(f"**{i.get('q') or ''}**\n{i.get('a') or ''}\n\n" for i in _md_items(p.get("items")))
    if t == "testimonials":
        # Customer words, not the company's claims: marked so agents don't treat them as facts.
        return head(2) + "".join(f"> {i.get('quote') or ''} — {i.get('name') or ''}"
                                 + (f", {i['role']}" if i.get("role") else "") + " *(customer quote)*\n\n"
                                 for i in _md_items(p.get("items")))
    if t == "logos":
        return head(2) + ", ".join(str(i.get("alt") or "") for i in _md_items(p.get("items")) if i.get("alt")) + "\n"
    if t == "comparison":
        cols = [_cell(c) for c in p.get("columns") or []]
        out = head(2) + "| | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols) + "\n"
        return out + "".join("| " + _cell(r.get("label")) + " | " + " | ".join(_cell(v) for v in r.get("values") or [])
                             + " |\n" for r in _md_items(p.get("rows")))
    if t == "media":
        return (f"![{p.get('alt') or ''}]({p['src']})\n\n" if p.get("src") else "") + (f"{p['caption']}\n" if p.get("caption") else "")
    if t == "flowchart":
        return "".join(f"{n + 1}. {i.get('label') or ''}\n" for n, i in enumerate(_md_items(p.get("nodes"))))
    if t == "chart":
        unit = f" {p['unit']}" if p.get("unit") else ""
        return head(2) + "| | |\n|---|---|\n" + "".join(f"| {_cell(d.get('label'))} | {_cell(d.get('value'))}{unit} |\n"
                                                     for d in _md_items(p.get("data")))
    if t == "roi_calculator":
        return f"## {p.get('title') or 'Estimate your return'}\n\nAn ROI calculator (interactive on the page).\n"
    if t == "enquiry_form":
        names = ", ".join(str(f.get("label") or f.get("name")) for f in _md_items(p.get("fields")))
        return head(2) + f"A form on the page asks for: {names}.\n"
    # Customer components: their props as plain text.
    lines = []
    for k, v in p.items():
        if isinstance(v, (str, int, float)) and not str(k).startswith("_"):
            lines.append(f"- {k}: {v}")
    return "\n".join(lines) + ("\n" if lines else "")


def view_markdown(view: dict[str, Any]) -> str:
    regions = view.get("regions") or []
    first = regions[0] if regions else {}
    # A hero that carries the page title is the heading; don't say it twice.
    hero_title = first.get("renderer") == "hero" and (first.get("props") or {}).get("title") == view["title"]
    page_line = [f"Page: {view['url']}", ""] if view.get("url") else []
    out: list[str] = []
    if not hero_title:  # the title, then where the page is; otherwise that line follows the hero
        out, page_line = [f"# {view['title']}", ""] + page_line, []
    step_of = {rid: (n, st) for n, st in enumerate(view.get("flow") or []) for rid in st.get("regions") or []}
    current = None
    total = len(view.get("flow") or [])
    for r in view["regions"]:
        st = step_of.get(r["id"])
        if st and st[0] != current:
            current = st[0]
            out += [f"---\n\n**Step {st[0] + 1} of {total}: {st[1].get('title') or st[1]['step']}**", ""]
        md = section_markdown({"type": r["renderer"], "props": r["props"]}).strip()
        if md:
            out += [md, ""]
        if page_line and r is first:
            out += page_line
            page_line = []
    if view.get("actions"):
        out += ["## Actions", ""]
        for a in view["actions"]:
            how = {"auto": "an agent can do this", "confirm": "an agent needs its person's approval",
                   "never": "a person must do this on the page"}[a["policy"]]
            out.append(f"- `{a['id']}` — {a['label']} ({how})")
        out.append("")
    out += [f"_View {view['plan_id']} · the same content people see on the page._", ""]
    return "\n".join(out)


VIEW_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "fb.view/1",
    "title": "FluidBuddha view",
    "description": "A page as agents see it: the same plan, data and actions people see.",
    "type": "object",
    "required": ["schema", "plan_id", "title", "regions", "actions"],
    "properties": {
        "schema": {"const": SCHEMA},
        "plan_id": {"type": "string", "pattern": "^pl_[0-9a-f]{10}$"},
        "title": {"type": "string"},
        "url": {"type": "string"},
        "path": {"type": "string"},
        "route": {"type": "string"},
        "lang": {"type": "string"},
        "regions": {"type": "array", "items": {"type": "object", "required": ["id", "component", "renderer", "props"],
                    "properties": {"id": {"type": "string"}, "component": {"type": "string"},
                                   "renderer": {"type": "string"}, "width": {"enum": ["half"]},
                                   "step": {"type": "string"}, "props": {"type": "object"}}}},
        "flow": {"type": "array", "items": {"type": "object", "properties": {
            "step": {"type": "string"}, "title": {"type": "string"},
            "regions": {"type": "array", "items": {"type": "string"}}}}},
        "actions": {"type": "array", "items": {"type": "object", "required": ["id", "label", "kind", "policy"],
                    "properties": {"id": {"type": "string"}, "label": {"type": "string"},
                                   "kind": {"enum": ["site_action", "api"]}, "policy": {"enum": list(POLICIES)},
                                   "description": {"type": "string"}, "inputs": {"type": "object"}}}},
        "json_ld": {"type": "object"},
        "links": {"type": "object"},
    },
}


# ---- views ----------------------------------------------------------------------------------

def build_view(*, plan: dict[str, Any], sections: list[dict[str, Any]], site: dict[str, Any], plan_id: str,
               title: str, url: str, path: str, route: str, lang: str, links: dict[str, str],
               ld: dict[str, Any]) -> dict[str, Any]:
    flow = plan.get("flow") or []
    step_of = {rid: st["step"] for st in flow for rid in st.get("regions") or []}
    regions = []
    for s in sections:
        r: dict[str, Any] = {"id": s.get("id"), "component": s.get("component"), "renderer": s.get("type"),
                             "props": s.get("props") or {}}
        if s.get("width") == "half":
            r["width"] = "half"
        if step_of.get(str(s.get("id"))):
            r["step"] = step_of[str(s.get("id"))]
        regions.append(r)
    return {"schema": SCHEMA, "plan_id": plan_id, "title": title, "url": url, "path": path, "route": route,
            "lang": lang, "regions": regions, "flow": flow,
            "actions": describe_actions(plan, sections, site["site_key"]), "json_ld": ld, "links": links}


# ---- confirmation codes and running actions -----------------------------------------------------

def _digest(inputs: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(inputs or {}, sort_keys=True, default=str).encode()).hexdigest()


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def create_confirmation(db: AsyncSession, site_key: str, plan_id: str, action: str, inputs: dict[str, Any],
                              token_id: Any, summary: str) -> str:
    code = "fbc_" + secrets.token_urlsafe(18)
    await db.execute(text(
        "INSERT INTO agent_confirmations (code_hash, site_key, plan_id, action, inputs_hash, token_id, summary, "
        "expires_at) VALUES (:h, :sk, :p, :a, :ih, :t, :s, now() + make_interval(secs => :ttl))"),
        {"h": _code_hash(code), "sk": site_key, "p": plan_id, "a": action, "ih": _digest(inputs), "t": token_id,
         "s": summary[:300], "ttl": CONFIRM_TTL_S})
    await db.commit()
    return code


async def consume_confirmation(db: AsyncSession, site_key: str, plan_id: str, action: str,
                               inputs: dict[str, Any], code: str) -> bool:
    """True once for a live code issued for exactly this plan, action and inputs."""
    if not code or not code.startswith("fbc_") or len(code) > 64:
        return False
    res = await db.execute(text(
        "UPDATE agent_confirmations SET used_at = now() WHERE code_hash = :h AND site_key = :sk AND plan_id = :p "
        "AND action = :a AND inputs_hash = :ih AND used_at IS NULL AND expires_at > now()"),
        {"h": _code_hash(code), "sk": site_key, "p": plan_id, "a": action, "ih": _digest(inputs)})
    await db.commit()
    return (res.rowcount or 0) > 0


def _summary(action: dict[str, Any], inputs: dict[str, Any]) -> str:
    shown = ", ".join(f"{k}: {v}" for k, v in list((inputs or {}).items())[:6])
    return f"{action['label']}" + (f" ({shown})" if shown else "")


async def run_action(db: AsyncSession, site: dict[str, Any], view: dict[str, Any], action_id: str,
                     inputs: dict[str, Any], token: Optional[dict[str, Any]], confirm_code: str = ""
                     ) -> dict[str, Any]:
    """Run one of a view's actions for an agent, under its policy.

    Answers ``{"status": done | failed | needs_confirmation | refused, ...}``."""
    from app.agents import tools
    from app.apis.registry import get_site_apis

    action = next((a for a in view["actions"] if a["id"] == action_id), None)
    if action is None:
        return {"status": "refused", "message": f"This view has no action {action_id!r}."}
    if not isinstance(inputs, dict):
        return {"status": "refused", "message": "inputs must be an object."}
    if action["policy"] == "never":
        return {"status": "refused", "policy": "never",
                "message": f"A person must do this on the page: {view.get('url') or view['path']}"}
    if not token or "actions" not in token.get("scopes", []):
        return {"status": "refused", "message": "This needs a token from the site's owner with the 'actions' scope."}
    missing = [k for k in (action.get("inputs") or {}).get("required") or [] if inputs.get(k) in (None, "")]
    if missing:
        return {"status": "refused", "message": "Missing inputs: " + ", ".join(missing)}
    if action["policy"] == "confirm":
        if not confirm_code:
            summary = _summary(action, inputs)
            code = await create_confirmation(db, site["site_key"], view["plan_id"], action_id, inputs,
                                             token.get("id"), summary)
            return {"status": "needs_confirmation", "summary": summary, "confirm_code": code,
                    "expires_in": CONFIRM_TTL_S,
                    "message": "Ask the person you are acting for to approve this, then call again with the same "
                               "inputs and confirm_code."}
        if not await consume_confirmation(db, site["site_key"], view["plan_id"], action_id, inputs, confirm_code):
            return {"status": "refused",
                    "message": "That confirmation code isn't valid for these inputs (wrong, used or expired)."}
    try:
        if action["kind"] == "site_action":
            out = await tools.run_action(site, "action_" + action["ref"][7:], inputs, token.get("id"))
            ok = out.get("status") in ("done", "paid")
            return {"status": "done" if ok else "failed", "result": out}
        res = await get_site_apis(site["site_key"]).call(action["ref"][4:], inputs)
        return {"status": "done" if res.get("ok") else "failed", "result": res}
    except tools.ToolError as exc:
        return {"status": "failed", "message": str(exc)}
