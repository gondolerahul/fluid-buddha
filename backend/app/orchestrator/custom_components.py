"""
Components a tenant registers (M2-8), shown by the agent like built-in ones.

Two kinds, neither puts the tenant's JavaScript on the visitor's page:

* ``template`` — a declarative spec over a built-in component. The tenant
  gives a props schema (a small JSON-schema subset) and a ``base`` component
  (e.g. ``configurator``) whose state uses ``{{prop}}`` placeholders. When the
  agent renders it, its props are checked against the schema and filled in;
  the widget only ever draws the built-in base component.
* ``iframe`` — the tenant's own page at a registered https URL, drawn in a
  sandboxed iframe (scripts only: no same-origin, no top navigation, no
  forms, no popups). The URL comes from the registration, never from the
  agent. The widget and the frame talk only through a fixed postMessage
  contract: the widget sends ``{type: "fb:init", props}``; the frame may send
  ``{type: "fb:resize", height}`` and ``{type: "fb:state", state}``.

The agent sees enabled components in ``render_component`` (name, label,
description and props), read from an in-process cache like the profile.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.components import KNOWN_COMPONENTS

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
PROP_RE = re.compile(r"^[a-z][a-zA-Z0-9_]{0,30}$")
PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
PROP_TYPES = ("string", "number", "integer", "boolean", "array")
ITEM_TYPES = ("string", "number", "object")
MAX_PROPS = 20
MAX_TEMPLATE_BYTES = 20_000
MAX_ITEMS = 48
STRING_MAX = 500
_TTL_S = 30.0


class ComponentSpecError(ValueError):
    """The tenant's component registration is invalid (shown in the console)."""


class PropsError(ValueError):
    """The agent's props don't fit the component (told back to the model)."""


@dataclass
class CustomComponent:
    id: uuid.UUID
    site_key: str
    name: str
    label: str
    description: str
    kind: str
    props_schema: dict[str, Any]
    template: Optional[dict[str, Any]]
    iframe_url: Optional[str]
    enabled: bool

    def public(self) -> dict[str, Any]:
        return {"id": str(self.id), "name": self.name, "label": self.label,
                "description": self.description, "kind": self.kind,
                "props_schema": self.props_schema, "template": self.template,
                "iframe_url": self.iframe_url, "enabled": self.enabled}


# ---- the registration ---------------------------------------------------------

def _scalar_schema(key: str, p: Any, *, item: bool = False) -> dict[str, Any]:
    if not isinstance(p, dict):
        raise ComponentSpecError(f"prop {key}: needs a type")
    types = ITEM_TYPES if item else PROP_TYPES
    t = p.get("type")
    if t not in types:
        raise ComponentSpecError(f"prop {key}: type must be one of {', '.join(types)}")
    out: dict[str, Any] = {"type": t}
    if p.get("description"):
        out["description"] = " ".join(str(p["description"]).split())[:200]
    if t == "string" and p.get("enum") is not None:
        enum = [str(e)[:80] for e in p["enum"]] if isinstance(p["enum"], list) else []
        if not 1 <= len(enum) <= 30:
            raise ComponentSpecError(f"prop {key}: enum needs 1 to 30 values")
        out["enum"] = enum
    if t in ("number", "integer"):
        for b in ("minimum", "maximum"):
            if p.get(b) is not None:
                if not isinstance(p[b], (int, float)) or isinstance(p[b], bool):
                    raise ComponentSpecError(f"prop {key}: {b} must be a number")
                out[b] = p[b]
    if t == "object":
        props = p.get("properties")
        if not isinstance(props, dict) or not 1 <= len(props) <= 10:
            raise ComponentSpecError(f"prop {key}: an object item needs 1 to 10 properties")
        out["properties"] = {}
        for k, sub in props.items():
            if not PROP_RE.match(k):
                raise ComponentSpecError(f"prop {key}.{k}: bad name")
            s = _scalar_schema(f"{key}.{k}", sub, item=True)
            if s["type"] == "object":
                raise ComponentSpecError(f"prop {key}.{k}: objects can't nest")
            out["properties"][k] = s
    if t == "array":
        out["items"] = _scalar_schema(f"{key}[]", p.get("items"), item=True)
        out["maxItems"] = max(1, min(MAX_ITEMS, int(p.get("maxItems") or MAX_ITEMS)))
    if "default" in p:
        out["default"] = p["default"]
    return out


def clean_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("type", "object") != "object":
        raise ComponentSpecError('props schema must be {"type": "object", "properties": {…}}')
    props = raw.get("properties")
    if not isinstance(props, dict) or not 1 <= len(props) <= MAX_PROPS:
        raise ComponentSpecError(f"declare 1 to {MAX_PROPS} props")
    clean = {}
    for k, p in props.items():
        if not PROP_RE.match(str(k)):
            raise ComponentSpecError(f"prop name {k!r}: start with a letter; letters, digits, _")
        clean[k] = _scalar_schema(k, p)
    required = [r for r in raw.get("required") or [] if r in clean]
    schema = {"type": "object", "properties": clean, "required": required}
    for k, p in clean.items():   # defaults must themselves be valid
        if "default" in p:
            try:
                _value(k, p, p["default"])
            except PropsError as exc:
                raise ComponentSpecError(f"default of {k}: {exc}")
    return schema


def clean_spec(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name") or "").strip()
    if not NAME_RE.match(name):
        raise ComponentSpecError("name: 2-40 lowercase letters, digits or _, starting with a letter")
    if name in KNOWN_COMPONENTS or name == "embed":
        raise ComponentSpecError(f"{name} is a built-in component; pick another name")
    label = " ".join(str(data.get("label") or "").split())[:80]
    if not label:
        raise ComponentSpecError("add a label")
    kind = data.get("kind")
    if kind not in ("template", "iframe"):
        raise ComponentSpecError("kind must be template or iframe")
    schema = clean_schema(data.get("props_schema"))
    out: dict[str, Any] = {
        "name": name, "label": label, "kind": kind, "props_schema": schema,
        "description": " ".join(str(data.get("description") or "").split())[:400],
        "enabled": bool(data.get("enabled", True)), "template": None, "iframe_url": None,
    }
    if kind == "template":
        t = data.get("template")
        if not isinstance(t, dict) or t.get("base") not in KNOWN_COMPONENTS:
            raise ComponentSpecError("template needs a base: one of the built-in components")
        state = t.get("state")
        if not isinstance(state, dict):
            raise ComponentSpecError("template needs a state object")
        if len(json.dumps(state)) > MAX_TEMPLATE_BYTES:
            raise ComponentSpecError("template is too large")
        unknown = sorted(set(PLACEHOLDER.findall(json.dumps(state))) - set(schema["properties"]))
        if unknown:
            raise ComponentSpecError(f"template uses undeclared props: {', '.join(unknown)}")
        out["template"] = {"base": t["base"], "state": state}
    else:
        url = str(data.get("iframe_url") or "").strip()
        if not url.startswith("https://") or len(url) > 500 or any(c in url for c in " \"'<>\r\n\t"):
            raise ComponentSpecError("iframe URL must be an https:// link")
        out["iframe_url"] = url
    return out


# ---- the agent's props --------------------------------------------------------

def _value(key: str, s: dict[str, Any], v: Any) -> Any:
    t = s["type"]
    if t == "string":
        if not isinstance(v, (str, int, float)) or isinstance(v, bool):
            raise PropsError(f"{key} must be text")
        v = str(v)[:STRING_MAX]
        if "enum" in s and v not in s["enum"]:
            raise PropsError(f"{key} must be one of: {', '.join(s['enum'])}")
        return v
    if t in ("number", "integer"):
        if isinstance(v, bool):
            raise PropsError(f"{key} must be a number")
        try:
            v = int(v) if t == "integer" else float(v)
        except (TypeError, ValueError):
            raise PropsError(f"{key} must be a number")
        if ("minimum" in s and v < s["minimum"]) or ("maximum" in s and v > s["maximum"]):
            raise PropsError(f"{key} is out of range")
        return v
    if t == "boolean":
        if not isinstance(v, bool):
            raise PropsError(f"{key} must be true or false")
        return v
    if t == "object":
        if not isinstance(v, dict):
            raise PropsError(f"{key} must be an object")
        return {k: _value(f"{key}.{k}", sub, v[k]) for k, sub in s["properties"].items() if k in v}
    if not isinstance(v, list):
        raise PropsError(f"{key} must be a list")
    return [_value(f"{key}[{i}]", s["items"], x) for i, x in enumerate(v[:s.get("maxItems", MAX_ITEMS)])]


def validate_props(schema: dict[str, Any], props: Any) -> dict[str, Any]:
    props = props if isinstance(props, dict) else {}
    out = {}
    for k, s in schema["properties"].items():
        if k in props and props[k] is not None:
            out[k] = _value(k, s, props[k])
        elif "default" in s:
            out[k] = s["default"]
        elif k in schema.get("required", []):
            raise PropsError(f"{k} is required")
    return out


def expand(node: Any, props: dict[str, Any]) -> Any:
    """Fill ``{{prop}}`` placeholders: a string that is only a placeholder
    takes the prop's value (number, list…); inside text it becomes text."""
    if isinstance(node, dict):
        return {k: expand(v, props) for k, v in node.items()}
    if isinstance(node, list):
        return [expand(v, props) for v in node]
    if isinstance(node, str):
        whole = PLACEHOLDER.fullmatch(node.strip())
        if whole:
            return props.get(whole.group(1))
        return PLACEHOLDER.sub(lambda m: "" if props.get(m.group(1)) is None
                               else str(props.get(m.group(1))), node)
    return node


def render(c: CustomComponent, props: Any) -> tuple[str, dict[str, Any]]:
    """(component_type, state) the widget draws. Raises PropsError."""
    clean = validate_props(c.props_schema, props)
    if c.kind == "template":
        return c.template["base"], expand(c.template["state"], clean)
    return "embed", {"src": c.iframe_url, "name": c.name, "props": clean}


def describe(c: CustomComponent) -> str:
    """One line for the agent's component list."""
    req = set(c.props_schema.get("required", []))
    props = ", ".join(
        f"{k} ({s['type']}{', one of ' + '/'.join(s['enum']) if 'enum' in s else ''}"
        f"{', required' if k in req else ''})" for k, s in c.props_schema["properties"].items())
    return f"- {c.name}: {c.label}. {c.description} initial_state = props {{{props}}}"


# ---- storage + cache ------------------------------------------------------------

def _row(r: Any) -> CustomComponent:
    j = lambda v: v if isinstance(v, (dict, list)) or v is None else json.loads(v)  # noqa: E731
    return CustomComponent(id=r["id"], site_key=r["site_key"], name=r["name"], label=r["label"],
                           description=r["description"], kind=r["kind"],
                           props_schema=j(r["props_schema"]), template=j(r["template"]),
                           iframe_url=r["iframe_url"], enabled=r["enabled"])


async def list_components(db: AsyncSession, site_key: str) -> list[CustomComponent]:
    rows = (await db.execute(text(
        "SELECT * FROM site_components WHERE site_key = :s ORDER BY created_at"),
        {"s": site_key})).mappings().all()
    return [_row(r) for r in rows]


async def save_component(db: AsyncSession, site_key: str, data: dict[str, Any],
                         component_id: Optional[uuid.UUID] = None) -> CustomComponent:
    spec = clean_spec(data)
    clash = (await db.execute(text(
        "SELECT 1 FROM site_components WHERE site_key = :s AND name = :n AND id <> :id"),
        {"s": site_key, "n": spec["name"], "id": component_id or uuid.uuid4()})).first()
    if clash:
        raise ComponentSpecError(f"another component is already called {spec['name']}")
    params = {**spec, "s": site_key, "ps": json.dumps(spec["props_schema"]),
              "t": json.dumps(spec["template"]) if spec["template"] else None}
    if component_id:
        r = (await db.execute(text(
            "UPDATE site_components SET name = :name, label = :label, description = :description, "
            "kind = :kind, props_schema = CAST(:ps AS jsonb), template = CAST(:t AS jsonb), "
            "iframe_url = :iframe_url, enabled = :enabled, updated_at = now() "
            "WHERE id = :id AND site_key = :s RETURNING *"), {**params, "id": component_id})
        ).mappings().first()
        if r is None:
            raise LookupError("no such component")
    else:
        r = (await db.execute(text(
            "INSERT INTO site_components (id, site_key, name, label, description, kind, "
            "props_schema, template, iframe_url, enabled) VALUES (:id, :s, :name, :label, "
            ":description, :kind, CAST(:ps AS jsonb), CAST(:t AS jsonb), :iframe_url, :enabled) "
            "RETURNING *"), {**params, "id": uuid.uuid4()})).mappings().one()
    invalidate(site_key)
    return _row(r)


async def delete_component(db: AsyncSession, site_key: str, component_id: uuid.UUID) -> bool:
    res = await db.execute(text("DELETE FROM site_components WHERE id = :id AND site_key = :s"),
                           {"id": component_id, "s": site_key})
    invalidate(site_key)
    return (res.rowcount or 0) > 0


_cache: dict[str, tuple[float, list[CustomComponent]]] = {}


def invalidate(site_key: str) -> None:
    _cache.pop(site_key, None)


def components_for(site_key: Optional[str]) -> dict[str, CustomComponent]:
    hit = _cache.get(site_key or "")
    return {c.name: c for c in hit[1] if c.enabled} if hit else {}


async def ensure_components(db: AsyncSession, site_key: str) -> dict[str, CustomComponent]:
    hit = _cache.get(site_key)
    if not hit or time.monotonic() - hit[0] >= _TTL_S:
        _cache[site_key] = (time.monotonic(), await list_components(db, site_key))
    return components_for(site_key)
