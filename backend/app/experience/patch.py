"""
Plan patches (P2-4): the conversation edits the page on screen.

    ops: [{op: "add",     region, component, props, before?, animation?},
          {op: "replace", region, component?, props, animation?},
          {op: "remove",  region},
          {op: "move",    region, before?}]

``apply_ops`` applies them to a stored plan; the result is validated like any
plan (same manifest, source rules and bindings), and only the regions that were
added or replaced are bound and sent to the page, so a patch never re-renders
what the visitor is already looking at.
"""
from __future__ import annotations

import copy
from typing import Any

from app.experience.plan import MAX_REGIONS, slug

OPS = ("add", "replace", "remove", "move")
ANIMATIONS = ("fade", "highlight", "count_up")
MAX_OPS = 8


def apply_ops(plan: dict[str, Any], ops: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Returns ``(patched raw plan, accepted ops, problems)``. The patched plan
    keeps its ``plan_id`` (it is the same page, edited)."""
    problems: list[str] = []
    new = copy.deepcopy(plan)
    regions: list[dict[str, Any]] = list(new.get("regions") or [])
    accepted: list[dict[str, Any]] = []
    if not isinstance(ops, list) or not ops:
        return new, [], ["ops must be a non-empty list"]

    def index(rid: str) -> int:
        return next((i for i, r in enumerate(regions) if r.get("id") == rid), -1)

    for raw in ops[:MAX_OPS]:
        if not isinstance(raw, dict) or raw.get("op") not in OPS:
            problems.append(f"unknown op {raw!r}; use add, replace, remove or move")
            continue
        op, rid = raw["op"], slug(raw.get("region"))
        if not rid:
            problems.append(f"{op}: needs a region id")
            continue
        anim = raw.get("animation") if raw.get("animation") in ANIMATIONS else None
        i = index(rid)
        if op == "add":
            if i >= 0:
                problems.append(f"add: region {rid} already exists; use replace")
                continue
            if len(regions) >= MAX_REGIONS:
                problems.append(f"add: a page has at most {MAX_REGIONS} regions")
                continue
            region = {"id": rid, "component": str(raw.get("component") or ""),
                      "props": raw.get("props") if isinstance(raw.get("props"), dict) else {}}
            before = index(slug(raw.get("before"))) if raw.get("before") else -1
            regions.insert(before if before >= 0 else len(regions), region)
            accepted.append({"op": "add", "region": rid, "before": regions[before + 1]["id"]
                             if 0 <= before < len(regions) - 1 else None, "animation": anim or "fade"})
        elif op == "replace":
            if i < 0:
                problems.append(f"replace: no region {rid} on the page")
                continue
            region = dict(regions[i])
            if raw.get("component"):
                region["component"] = str(raw["component"])
            if isinstance(raw.get("props"), dict):
                region["props"] = raw["props"]
            regions[i] = region
            accepted.append({"op": "replace", "region": rid, "animation": anim or "highlight"})
        elif op == "remove":
            if i < 0:
                problems.append(f"remove: no region {rid} on the page")
                continue
            regions.pop(i)
            accepted.append({"op": "remove", "region": rid})
        elif op == "move":
            if i < 0:
                problems.append(f"move: no region {rid} on the page")
                continue
            region = regions.pop(i)
            before = index(slug(raw.get("before"))) if raw.get("before") else -1
            regions.insert(before if before >= 0 else len(regions), region)
            accepted.append({"op": "move", "region": rid,
                             "before": regions[before + 1]["id"] if 0 <= before < len(regions) - 1 else None})
    new["regions"] = regions
    return new, accepted, problems


def outline(plan: dict[str, Any]) -> str:
    """A compact description of the page on screen, for the model's prompt."""
    parts = []
    for r in plan.get("regions") or []:
        props = r.get("props") or {}
        bits = []
        for k, v in list(props.items())[:4]:
            if isinstance(v, dict) and "bind" in v:
                bits.append(f"{k}=<{v['bind']}>")
            elif isinstance(v, str):
                bits.append(f"{k}={v[:40]!r}")
            elif isinstance(v, list):
                bits.append(f"{k}=[{len(v)} items]")
        parts.append(f"{r.get('id')}: {r.get('component')}({', '.join(bits)})")
    return (f"ON-SCREEN PAGE (plan {plan.get('plan_id')}): " + "; ".join(parts) +
            ". To change it, call `patch_plan` with ops (add / replace / remove / move by region id); "
            "don't build a new page for an edit.")
