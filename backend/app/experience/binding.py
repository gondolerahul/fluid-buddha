"""
Data binding (strategy §4.6).

Resolves the bindings in a validated plan into render-ready props:

* ``api:<operationId>`` — a *read* operation of the site's API catalogue,
  called with ``params`` (literal values or ``ctx.<name>``);
* ``ctx.<name>``        — a value from the request context;
* ``entity:<Type>``     — the site's structured records (P2-6): one by
  ``params.key`` or a list filtered by ``params.where`` / ``params.limit``;
* ``content:search``    — site knowledge snippets for ``params.query``.

Param values may also be ``route.<name>`` (a parameter of the matched route).

Then ``path`` (a small JSONPath subset: ``$``, ``.key``, ``[n]``, ``[*]``)
selects from the response and ``transform`` (``count``, ``first``,
``limit:<n>``, ``sort_by:<key>``, ``sort_by_desc:<key>``) shapes it. No
arbitrary code runs.

The model never sees bound values: they go straight to the renderer. A region
whose required prop resolves to nothing is ``empty``; one whose required
binding failed is ``error``. Either way the renderer draws nothing for it
rather than inventing data.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from app.experience.manifest import ComponentManifest, PropSpec
from app.experience.plan import Plan, is_binding

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\.([A-Za-z0-9_]+)|\[(\d+)\]|\[(\*)\]")
_FAILED = object()


@dataclass
class BoundRegion:
    id: str
    component: str
    renderer: str
    props: dict[str, Any]
    state: str = "ready"            # ready | empty | error
    width: str = "full"

    def to_section(self) -> dict[str, Any]:
        """The v1.0 ``PageSection`` shape plus the plan addressing fields."""
        d = {
            "type": self.renderer,
            "props": self.props,
            "id": self.id,
            "component": self.component,
            "state": self.state,
        }
        if self.width == "half":
            d["width"] = "half"
        return d


def select(data: Any, path: Optional[str]) -> Any:
    """Evaluate a JSONPath-subset expression. ``[*]`` yields a list."""
    if not path or path == "$":
        return data
    cur: list[Any] = [data]
    multi = False
    for key, idx, star in _TOKEN_RE.findall(path[1:]):
        nxt: list[Any] = []
        for v in cur:
            if key:
                if isinstance(v, dict) and key in v:
                    nxt.append(v[key])
            elif idx:
                i = int(idx)
                if isinstance(v, list) and i < len(v):
                    nxt.append(v[i])
            elif isinstance(v, list):
                nxt.extend(v)
        multi = multi or bool(star)
        cur = nxt
    if multi:
        return cur
    return cur[0] if cur else None


def apply_transforms(value: Any, transforms: Optional[list[str]]) -> Any:
    for t in transforms or []:
        name, _, arg = t.partition(":")
        if name == "count":
            value = len(value) if isinstance(value, list) else (0 if value is None else 1)
        elif name == "first":
            value = value[0] if isinstance(value, list) and value else (
                None if isinstance(value, list) else value)
        elif name == "limit" and isinstance(value, list):
            value = value[: int(arg)]
        elif name in ("sort_by", "sort_by_desc") and isinstance(value, list):
            present: list[Any] = []
            absent: list[Any] = []
            for v in value:
                (present if isinstance(v, dict) and v.get(arg) is not None else absent).append(v)
            try:
                present.sort(key=lambda v: v[arg], reverse=(name == "sort_by_desc"))
            except TypeError:  # mixed types: keep the API's order
                pass
            value = present + absent
    return value


def apply_map(value: Any, fmap: Optional[dict[str, str]]) -> Any:
    """Rename fields of a record (or each record of a list) to a prop shape."""
    if not fmap:
        return value

    def one(rec: Any) -> Any:
        if not isinstance(rec, dict):
            return rec
        return {out: select(rec, "$." + src) for out, src in fmap.items() if select(rec, "$." + src) is not None}

    return [one(r) for r in value] if isinstance(value, list) else one(value)


def _fit(value: Any, spec: PropSpec) -> Any:
    """Shape a bound value to its prop spec; None when it doesn't fit."""
    if value is None:
        return None
    t = spec.type
    if t == "array":
        if not isinstance(value, list):
            return None
        return value[: spec.max_items] if spec.max_items else value
    if t == "string":
        if isinstance(value, (dict, list)):
            return None
        s = str(value)
        return s[: spec.max_length] if spec.max_length else s
    if t == "number":
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    if t == "boolean":
        return value if isinstance(value, bool) else None
    if t == "object":
        return value if isinstance(value, dict) else None
    return value


def _empty(value: Any) -> bool:
    return value is None or value == [] or value == ""


def _resolve_params(params: Mapping[str, Any], ctx: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    route = ctx.get("route") if isinstance(ctx.get("route"), dict) else {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("ctx."):
            v = ctx.get(v[4:])
        elif isinstance(v, str) and v.startswith("route."):
            v = route.get(v[6:])
        if v is not None:
            out[k] = v
    return out


Resolver = Callable[[str, dict[str, Any]], Awaitable[Any]]


async def bind_plan(
    plan: Plan,
    *,
    manifest: ComponentManifest,
    registry: Any,
    ctx: Optional[Mapping[str, Any]] = None,
    resolve: Optional[Resolver] = None,
) -> list[BoundRegion]:
    """``resolve(ref, params)`` answers ``entity:`` and ``content:`` bindings
    (they need the database); without it those bindings resolve to nothing."""
    ctx = dict(ctx or {})

    # One call per distinct (operation, params), all in parallel.
    calls: dict[str, tuple[str, dict[str, Any]]] = {}
    for region in plan.regions:
        for value in region.props.values():
            if is_binding(value) and value["bind"].startswith(("api:", "entity:", "content:")):
                params = _resolve_params(value.get("params") or {}, ctx)
                key = value["bind"] + "|" + json.dumps(params, sort_keys=True, default=str)
                calls.setdefault(key, (value["bind"], params))

    async def run(ref: str, params: dict[str, Any]) -> Any:
        if ref.startswith("api:"):
            return await registry.call(ref[4:], params)
        if resolve is None:
            return {"ok": False}
        return {"ok": True, "data": await resolve(ref, params)}

    responses: dict[str, Any] = {}
    if calls:
        keys = list(calls)
        results = await asyncio.gather(
            *(run(ref, params) for ref, params in calls.values()),
            return_exceptions=True,
        )
        for key, res in zip(keys, results):
            if isinstance(res, Exception) or not isinstance(res, dict) or not res.get("ok"):
                logger.info("binding call %s failed: %s", key.split("|", 1)[0], res)
                responses[key] = _FAILED
            else:
                responses[key] = res.get("data")

    bound: list[BoundRegion] = []
    for region in plan.regions:
        entry = manifest.get(region.component)
        if entry is None:  # validated plans only hold known components
            continue
        props: dict[str, Any] = {}
        state = "ready"
        for name, value in region.props.items():
            spec = entry.props.get(name, PropSpec())
            if not is_binding(value):
                props[name] = value
                continue
            ref = value["bind"]
            if ref.startswith(("api:", "entity:", "content:")):
                params = _resolve_params(value.get("params") or {}, ctx)
                key = ref + "|" + json.dumps(params, sort_keys=True, default=str)
                raw = responses.get(key, _FAILED)
            else:
                raw = ctx.get(ref[4:])
            if raw is _FAILED:
                if spec.required:
                    state = "error"
                continue
            result = _fit(apply_map(apply_transforms(select(raw, value.get("path")), value.get("transform")),
                                    value.get("map")), spec)
            if _empty(result):
                if spec.required and state == "ready":
                    state = "empty"
                continue
            props[name] = result
        bound.append(BoundRegion(
            id=region.id, component=region.component, renderer=entry.renderer,
            props=props, state=state, width=getattr(region, "width", "full"),
        ))
    return bound
