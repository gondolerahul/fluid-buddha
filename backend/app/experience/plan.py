"""
Experience Plan schema ``fb.plan/1`` and its validator (strategy §3.3, §4.3).

A plan describes a view: ordered regions, each using one manifest component
with props, where a prop is either a literal the model wrote or a *binding*
(a reference to data resolved later by ``binding.py``). Every plan — from the
model, a cache, a pinned layout or the mock engine — passes ``validate_plan``
before it reaches a client.

The validator never raises on bad input. It returns the safest plan it can
build plus a list of problems phrased so the model can fix its next call.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any, Optional

from app.experience.manifest import ComponentManifest, ManifestEntry, PropSpec

SCHEMA = "fb.plan/1"
MAX_REGIONS = 12
MAX_ACTIONS = 8

# Request-context paths a binding (or binding param) may read.
CTX_PATHS = frozenset({"currency", "lang", "page", "persona", "site_key"})
CONFIRMS = ("none", "card", "typed")

_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_TRANSFORM_RE = re.compile(r"^(count|first|limit:\d{1,3}|sort_by(_desc)?:[A-Za-z0-9_]{1,40})$")
_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,60}$")
_ENTITY_RE = re.compile(r"^[A-Z][A-Za-z0-9]{0,39}$")
_ROUTE_PARAM_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
_PATH_RE = re.compile(r"^\$(\.[A-Za-z0-9_]+|\[\d+\]|\[\*\])*$")


def new_plan_id() -> str:
    return f"pl_{secrets.token_hex(5)}"


def slug(text: Any, max_len: int = 40) -> str:
    s = _SLUG_RE.sub("-", str(text or "").strip().lower().replace("_", "-")).strip("-")
    return s[:max_len].strip("-")


def is_binding(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("bind"), str)


@dataclass
class Region:
    id: str
    component: str
    props: dict[str, Any]
    width: str = "full"           # full | half (free composition in a two-column grid, Phase 4)

    def to_dict(self) -> dict[str, Any]:
        d = {"id": self.id, "component": self.component, "props": self.props}
        if self.width == "half":
            d["width"] = "half"
        return d


@dataclass
class PlanAction:
    id: str
    ref: str
    confirm: str = "card"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "ref": self.ref, "confirm": self.confirm}


@dataclass
class Plan:
    plan_id: str
    site_key: str
    title: str
    regions: list[Region] = field(default_factory=list)
    actions: list[PlanAction] = field(default_factory=list)
    intent: dict[str, Any] = field(default_factory=dict)
    layout: str = ""
    theme: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    # A multi-step flow (Phase 4): [{step, title, regions: [region ids]}]; empty = one page.
    flow: list[dict[str, Any]] = field(default_factory=list)
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "schema": self.schema,
            "site_key": self.site_key,
            "title": self.title,
            "intent": self.intent,
            "layout": self.layout,
            "theme": self.theme,
            "regions": [r.to_dict() for r in self.regions],
            "actions": [a.to_dict() for a in self.actions],
            "policies": self.policies,
            "provenance": self.provenance,
            **({"flow": self.flow} if self.flow else {}),
        }


@dataclass
class PlanReport:
    plan: Plan
    problems: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.dropped


def validate_plan(
    raw: Any,
    *,
    manifest: ComponentManifest,
    catalogue: Optional[Any] = None,
    site_key: str = "",
) -> PlanReport:
    raw = raw if isinstance(raw, dict) else {}
    problems: list[str] = []
    dropped: list[str] = []

    plan = Plan(
        plan_id=_plan_id(raw.get("plan_id")),
        site_key=site_key or str(raw.get("site_key") or ""),
        title=(str(raw.get("title") or "").strip() or "Untitled")[:160],
        intent=raw.get("intent") if isinstance(raw.get("intent"), dict) else {},
        layout=str(raw.get("layout") or "")[:80],
        theme=raw.get("theme") if isinstance(raw.get("theme"), dict) else {},
        policies=raw.get("policies") if isinstance(raw.get("policies"), dict) else {},
        provenance=raw.get("provenance") if isinstance(raw.get("provenance"), dict) else {},
    )

    plan.actions = _validate_actions(raw.get("actions"), catalogue, problems)
    action_ids = {a.id for a in plan.actions}

    used_ids: set[str] = set()
    regions_raw = raw.get("regions")
    if not isinstance(regions_raw, list):
        regions_raw = []
        problems.append("regions must be a list of {id?, component, props}")
    for i, r in enumerate(regions_raw):
        if len(plan.regions) >= MAX_REGIONS:
            dropped.append(f"regions after the first {MAX_REGIONS}")
            break
        if not isinstance(r, dict):
            dropped.append(f"region {i}: not an object")
            continue
        cid = str(r.get("component") or "").strip()
        entry = manifest.get(cid)
        if entry is None:
            dropped.append(f"region {i}: unknown component {cid!r}")
            continue
        rid = _region_id(r.get("id"), entry, used_ids)
        props = _validate_props(
            r.get("props"), entry, rid, catalogue, action_ids, problems)
        if props is None:
            dropped.append(f"region {rid}: required props missing")
            continue
        width = "half" if r.get("width") == "half" else "full"
        plan.regions.append(Region(id=rid, component=cid, props=props, width=width))

    plan.flow = _validate_flow(raw.get("flow"), {r.id for r in plan.regions}, problems)
    if plan.layout not in ("", "stack", "split"):
        plan.layout = ""
    must = plan.policies.get("must_include")
    if isinstance(must, list):
        present = {r.component for r in plan.regions}
        for cid in must:
            if str(cid) not in present:
                problems.append(f"policy: must include component {cid}")

    return PlanReport(plan=plan, problems=problems, dropped=dropped)


MAX_STEPS = 5


def _validate_flow(raw: Any, region_ids: set[str], problems: list[str]) -> list[dict[str, Any]]:
    """Steps that each name existing regions; fewer than two steps is no flow."""
    if not isinstance(raw, list) or not raw:
        return []
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in raw[:MAX_STEPS]:
        if not isinstance(s, dict):
            continue
        sid = slug(s.get("step"))
        regs = [slug(x) for x in (s.get("regions") or []) if slug(x) in region_ids]
        if not sid or sid in seen or not regs:
            problems.append(f"flow step {s.get('step')!r}: needs a unique id and existing regions")
            continue
        seen.add(sid)
        steps.append({"step": sid, "title": str(s.get("title") or sid)[:60], "regions": regs})
    return steps if len(steps) >= 2 else []


def _plan_id(v: Any) -> str:
    s = str(v or "")
    return s if re.fullmatch(r"pl_[0-9a-f]{10}", s) else new_plan_id()


def _region_id(raw_id: Any, entry: ManifestEntry, used: set[str]) -> str:
    """Stable id: the model's slug, else the component's short name; a numeric
    suffix keeps ids unique (hero, hero-2, …), so one plan shape always yields
    the same ids for agents and analytics (strategy §6.3)."""
    base = slug(raw_id) or slug(entry.short_name) or "region"
    rid, n = base, 2
    while rid in used:
        rid = f"{base}-{n}"
        n += 1
    used.add(rid)
    return rid


def _validate_actions(raw: Any, catalogue: Any, problems: list[str]) -> list[PlanAction]:
    out: list[PlanAction] = []
    if not isinstance(raw, list):
        return out
    seen: set[str] = set()
    for a in raw[:MAX_ACTIONS]:
        if not isinstance(a, dict):
            continue
        aid = slug(a.get("id"))
        ref = str(a.get("ref") or "").strip()
        if not aid or aid in seen:
            problems.append(f"action {a.get('id')!r}: needs a unique id")
            continue
        confirm = str(a.get("confirm") or "card")
        confirm = confirm if confirm in CONFIRMS else "card"
        if ref.startswith("api:"):
            op = catalogue.operation(ref[4:]) if catalogue is not None else None
            if op is None:
                problems.append(f"action {aid}: unknown operation {ref[4:]!r}")
                continue
            if op.effect == "read":
                problems.append(f"action {aid}: {ref[4:]} is a read; bind it instead")
                continue
            # Never weaker than the API's own requirement; destructive needs typed.
            floor = "typed" if op.effect == "destructive" else (op.confirm or "card")
            confirm = _stronger(confirm, floor if floor != "none" else "card")
        elif not (ref.startswith("action:") and len(ref) > 7):
            problems.append(f"action {aid}: ref must be 'action:<name>' or 'api:<operationId>'")
            continue
        seen.add(aid)
        out.append(PlanAction(id=aid, ref=ref, confirm=confirm))
    return out


def _stronger(a: str, b: str) -> str:
    return a if CONFIRMS.index(a) >= CONFIRMS.index(b) else b


def _validate_props(
    raw: Any, entry: ManifestEntry, rid: str, catalogue: Any,
    action_ids: set[str], problems: list[str],
) -> Optional[dict[str, Any]]:
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for name, value in raw.items():
        spec = entry.props.get(name)
        if spec is None:
            continue  # unknown props are dropped silently (as normalize_page)
        where = f"{rid}.{name}"
        if is_binding(value):
            if spec.source == "model_text":
                problems.append(f"{where}: must be written, not bound")
                continue
            b = _validate_binding(value, catalogue, where, problems)
            if b is not None:
                out[name] = b
            continue
        if spec.source == "binding_only":
            problems.append(f"{where}: must be a binding ({{\"bind\": \"api:<operationId>\"}})")
            continue
        if name == "action" and value not in (None, ""):
            if slug(value) not in action_ids:
                problems.append(f"{where}: unknown action {value!r}; declare it in actions")
                continue
            out[name] = slug(value)
            continue
        coerced = _coerce(value, spec)
        if coerced is _INVALID:
            problems.append(f"{where}: expected {spec.describe()}")
            continue
        out[name] = coerced
    missing = [n for n, s in entry.props.items() if s.required and n not in out]
    if missing:
        problems.append(f"{rid}: missing required props {', '.join(missing)}")
        return None
    return out


_INVALID = object()


def _coerce(value: Any, spec: PropSpec) -> Any:
    t = spec.type
    if t == "string":
        if isinstance(value, (dict, list)):
            return _INVALID
        s = str(value if value is not None else "").strip()
        if spec.enum and s not in spec.enum:
            return _INVALID
        return s[: spec.max_length] if spec.max_length else s
    if t == "number":
        if isinstance(value, bool):
            return _INVALID
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return _INVALID
    if t == "boolean":
        return value if isinstance(value, bool) else _INVALID
    if t == "array":
        if not isinstance(value, list):
            return _INVALID
        return value[: spec.max_items] if spec.max_items else value
    if t == "object":
        return value if isinstance(value, dict) else _INVALID
    return value


def _validate_binding(
    value: dict[str, Any], catalogue: Any, where: str, problems: list[str],
) -> Optional[dict[str, Any]]:
    ref = value["bind"].strip()
    out: dict[str, Any] = {"bind": ref}
    if ref.startswith("api:"):
        op_id = ref[4:]
        op = catalogue.operation(op_id) if catalogue is not None else None
        if op is None:
            problems.append(f"{where}: unknown operation {op_id!r}")
            return None
        if op.effect != "read":
            problems.append(f"{where}: {op_id} changes data; only read operations can be bound")
            return None
        if op.auth == "user":
            problems.append(f"{where}: {op_id} needs a signed-in user; not bindable here")
            return None
    elif ref.startswith("ctx."):
        if ref[4:] not in CTX_PATHS:
            problems.append(f"{where}: context {ref!r} is not available")
            return None
    elif ref.startswith("entity:"):
        # Structured records (P2-6): entity:<Type>, optional params key / where / limit.
        if not _ENTITY_RE.match(ref[7:]):
            problems.append(f"{where}: entity type {ref[7:]!r} must be a name such as Product")
            return None
    elif ref == "content:search":
        q = (value.get("params") or {}).get("query") if isinstance(value.get("params"), dict) else None
        if not isinstance(q, str) or not q.strip():
            problems.append(f"{where}: content:search needs params.query")
            return None
    else:
        problems.append(f"{where}: binding must be 'api:<operationId>', 'entity:<Type>', "
                        "'content:search' or 'ctx.<name>'")
        return None

    path = value.get("path")
    if path is not None:
        path = str(path).strip()
        if not _PATH_RE.match(path):
            problems.append(f"{where}: path {path!r} must look like $.a.b[0] or $.items[*]")
            return None
        out["path"] = path
    params = value.get("params")
    if params is not None:
        if not isinstance(params, dict):
            problems.append(f"{where}: params must be an object")
            return None
        clean: dict[str, Any] = {}
        for k, v in list(params.items())[:20]:
            if k == "where" and ref.startswith("entity:") and isinstance(v, dict)                     and all(not isinstance(x, (dict, list)) for x in v.values()):
                clean["where"] = {str(a): b for a, b in list(v.items())[:10]}
                continue
            if isinstance(v, (dict, list)):
                problems.append(f"{where}: param {k} must be a plain value")
                return None
            if isinstance(v, str) and v.startswith("route.") and not _ROUTE_PARAM_RE.match(v[6:]):
                problems.append(f"{where}: param {k} uses a bad route parameter {v!r}")
                return None
            if isinstance(v, str) and v.startswith("ctx.") and v[4:] not in CTX_PATHS:
                problems.append(f"{where}: param {k} uses unknown context {v!r}")
                return None
            clean[str(k)] = v
        out["params"] = clean
    fmap = value.get("map")
    if fmap is not None:
        # Rename record fields to a component's prop shape: {"title": "name", "body": "summary"}.
        if not (isinstance(fmap, dict) and fmap and len(fmap) <= 12 and all(
                isinstance(k, str) and isinstance(v, str) and _FIELD_RE.match(k) and _FIELD_RE.match(v)
                for k, v in fmap.items())):
            problems.append(f"{where}: map must be {{\"prop\": \"field\"}} with plain field names")
            return None
        out["map"] = dict(fmap)
    transform = value.get("transform")
    if transform is not None:
        items = transform if isinstance(transform, list) else [transform]
        bad = [t for t in items if not (isinstance(t, str) and _TRANSFORM_RE.match(t))]
        if bad:
            problems.append(f"{where}: unsupported transform {bad[0]!r}")
            return None
        out["transform"] = list(items)[:5]
    return out
