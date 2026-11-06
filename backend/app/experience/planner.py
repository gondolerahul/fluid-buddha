"""
G1 region planner (P1-3): fill a page's declared slots for an intent family.

    gather site material (CORTEX + pinned answers)
      → the model writes one region per slot from the slot's allowed components
        (a tool call constrained to the manifest), citing material
      → enforcement: region id = slot name, component allowed for the slot, any
        number in model-written text must appear in the material
      → the shared plan validator (props, source rules, bindings)

When there is no model (mock mode, past the rate or spend limit) or the
model's plan doesn't survive the checks, a rules composer fills hero / text /
CTA / feature grid / FAQ slots only from site material: it costs nothing and
never invents facts.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experience.intent import Intent, Signals
from app.experience.manifest import ComponentManifest, ManifestEntry
from app.experience.plan import validate_plan
from app.experience.regions_store import RegionSlot

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9ऀ-ॿ]+")
_NUM_RE = re.compile(r"\d[\d,.]*")
_STOP = {"the", "and", "for", "with", "you", "your", "our", "are", "that", "this", "from", "into", "have",
         "has", "can", "will", "what", "how", "who", "why", "when", "all", "any", "not", "but", "its"}

PLANNER_PROMPT = """You fill named slots on a business website's page for one visitor.

You know the visitor's likely goal (the INTENT) and the page they landed on. For EACH slot,
pick ONE component from that slot's allowed list and fill its props so the slot speaks to
that goal. Rules:
- Use ONLY facts from SOURCES. Cite the source ids you used in "sources".
- Never invent numbers, prices, customers or claims. Any number you write must appear in a source.
- For live data (prices, plans, stock, records) BIND the prop: {"bind": "api:<operationId>", "path": "$..."}.
- Props marked model_text are short copy you write; binding_only props must be bindings.
- Keep copy short and in the brand voice. Leave a slot out if the sources can't support it.
Call compose_regions once."""


@dataclass
class Material:
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)   # S1 → {text, label}
    golden: list[tuple[str, str]] = field(default_factory=list)        # pinned (q, a)

    def all_text(self) -> str:
        return " ".join([*(s["text"] for s in self.sources.values()), *(a for _, a in self.golden)])


def _words(s: str) -> set[str]:
    return {w for w in _WORD_RE.findall((s or "").lower()) if w not in _STOP and len(w) > 2}


def _sentences(s: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+|\n+", s or "")
    return [p.strip(" -•*#\t") for p in parts if 30 <= len(p.strip()) <= 320]


async def gather(db: AsyncSession, bridge: Any, site_key: str, intent: Intent, sig: Signals, *,
                 threshold: float, top_k: int = 6) -> Material:
    queries = [q for q in (f"{intent.label}. {intent.stage}".strip(" ."), sig.text(), sig.query) if q]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for q in queries:
        try:
            found = await bridge.search(q, top_k=top_k)
        except Exception as exc:
            logger.warning("region planner retrieval failed: %s", exc)
            found = []
        for r in found:
            body = (r.get("content") or "").strip()
            if not body or float(r.get("score") or 0) < threshold or body in seen:
                continue
            seen.add(body)
            rows.append(r)
    m = Material()
    for i, r in enumerate(rows[: top_k * 2], start=1):
        name = (r.get("source_ref") or {}).get("filename") or r.get("document_title") or "Site content"
        m.sources[f"S{i}"] = {"text": r["content"].strip()[:1500], "label": str(name)[:80]}
    gold = (await db.execute(text(
        "SELECT question, answer_text FROM conversation_cache WHERE site_key = :s AND kind = 'turn' "
        "AND status = 'pinned' ORDER BY hit_count DESC NULLS LAST LIMIT 12"), {"s": site_key})).all()
    m.golden = [(q, a) for q, a in gold if q and a]
    return m


def allowed_entries(slot: RegionSlot, manifest: ComponentManifest) -> list[ManifestEntry]:
    if slot.components:
        return [e for c in slot.components if (e := manifest.get(c)) is not None]
    return manifest.entries()


# ---- rules composer ----------------------------------------------------------

class _Picker:
    def __init__(self, m: Material, focus: set[str]) -> None:
        self.focus = focus
        self.used: set[str] = set()
        self.pool: list[tuple[str, str]] = [(k, s) for k, src in m.sources.items() for s in _sentences(src["text"])]
        self.labels = {k: src["label"] for k, src in m.sources.items()}

    def best(self, n: int = 1) -> list[tuple[str, str]]:
        ranked = sorted((p for p in self.pool if p[1] not in self.used),
                        key=lambda p: -len(_words(p[1]) & self.focus))
        out = ranked[:n]
        self.used.update(s for _, s in out)
        return out


def _fits(entry: ManifestEntry, props: dict[str, Any]) -> bool:
    return all(n in props for n, spec in entry.props.items() if spec.required) and \
        all(n in entry.props for n in props)


def _rules_region(slot: RegionSlot, entry: ManifestEntry, intent: Intent, m: Material,
                  pick: _Picker) -> Optional[dict[str, Any]]:
    r = entry.renderer
    props: dict[str, Any] = {}
    cites: list[str] = []
    if r == "hero":
        got = pick.best(1)
        if not got:
            return None
        props = {"title": intent.label if intent.family != "general" else slot.label or intent.label,
                 "subtitle": got[0][1]}
        cites = [got[0][0]]
    elif r == "text":
        got = pick.best(2)
        if not got:
            return None
        props = {"body": " ".join(s for _, s in got)}
        if slot.label:
            props["title"] = slot.label
        cites = [k for k, _ in got]
    elif r == "cta":
        got = pick.best(1)
        props = {"title": slot.label or intent.label, "cta_label": "Talk to us"}
        if got:
            props["body"] = got[0][1]
            cites = [got[0][0]]
    elif r == "feature_grid":
        got = pick.best(3)
        if len(got) < 2:
            return None
        props = {"title": slot.label or intent.label,
                 "items": [{"title": pick.labels.get(k, "Highlight"), "body": s} for k, s in got]}
        cites = [k for k, _ in got]
    elif r == "faq":
        if len(m.golden) < 2:
            return None
        ranked = sorted(m.golden, key=lambda qa: -len(_words(qa[0] + " " + qa[1]) & pick.focus))
        props = {"title": slot.label or "Questions", "items": [{"q": q, "a": a} for q, a in ranked[:5]]}
    else:
        return None
    if not _fits(entry, props):
        return None
    return {"id": slot.name, "component": entry.id, "props": props, "sources": cites}


def compose_rules(slots: list[RegionSlot], manifest: ComponentManifest, intent: Intent,
                  sig: Signals, m: Material) -> list[dict[str, Any]]:
    pick = _Picker(m, _words(f"{intent.label} {intent.stage} {sig.text()}"))
    out: list[dict[str, Any]] = []
    for slot in slots:
        for entry in allowed_entries(slot, manifest):
            region = _rules_region(slot, entry, intent, m, pick)
            if region:
                out.append(region)
                break
    return out


# ---- model composer -----------------------------------------------------------

def _tool_spec() -> Any:
    from app.ai.base import ToolSpec

    return ToolSpec(name="compose_regions", description="The content for the page's slots.", parameters={
        "type": "object", "properties": {
            "regions": {"type": "array", "items": {"type": "object", "properties": {
                "region": {"type": "string", "description": "the slot name"},
                "component": {"type": "string"},
                "props": {"type": "object"},
                "sources": {"type": "array", "items": {"type": "string"}}},
                "required": ["region", "component", "props"]}}},
        "required": ["regions"]})


def _prompt(slots: list[RegionSlot], manifest: ComponentManifest, intent: Intent, sig: Signals,
            m: Material, *, bindable: str, brand_voice: str) -> str:
    lines = [f"INTENT: {intent.label} (stage: {intent.stage or 'unknown'})",
             f"PAGE: {sig.page}", f"BRAND VOICE: {brand_voice}" if brand_voice else ""]
    if sig.utm_campaign or sig.query:
        lines.append(f"ARRIVED VIA: campaign={sig.utm_campaign or '-'} search={sig.query or '-'}")
    lines.append("SLOTS:")
    for s in slots:
        comps = "; ".join(e.to_prompt() for e in allowed_entries(s, manifest))
        lines.append(f"- {s.name}: {s.purpose or s.label or 'a page region'}. Allowed components: {comps}")
    if bindable:
        lines.append(bindable)
    lines.append("SOURCES:")
    lines += [f"[{k}] {src['text']}" for k, src in m.sources.items()]
    if m.golden:
        lines.append("APPROVED ANSWERS:")
        lines += [f"Q: {q} A: {a}" for q, a in m.golden]
    return "\n".join(x for x in lines if x)


async def compose_llm(llm: Any, model: Optional[str], slots: list[RegionSlot], manifest: ComponentManifest,
                      intent: Intent, sig: Signals, m: Material, *, bindable: str,
                      brand_voice: str) -> Optional[tuple[list[dict[str, Any]], int, int]]:
    from app.ai.base import ChatMessage

    try:
        resp = await llm.generate(
            system=PLANNER_PROMPT,
            messages=[ChatMessage(role="user", text=_prompt(slots, manifest, intent, sig, m,
                                                            bindable=bindable, brand_voice=brand_voice))],
            tools=[_tool_spec()], model=model, temperature=0.3, max_output_tokens=2500)
    except Exception as exc:
        logger.warning("region planning failed, using the rules: %s", exc)
        return None
    call = next((tc for tc in resp.tool_calls if tc.name == "compose_regions"), None)
    if call is None or not isinstance(call.args.get("regions"), list):
        return None
    out = []
    for r in call.args["regions"]:
        if isinstance(r, dict):
            out.append({"id": str(r.get("region") or ""), "component": str(r.get("component") or ""),
                        "props": r.get("props") if isinstance(r.get("props"), dict) else {},
                        "sources": [str(x) for x in (r.get("sources") or []) if isinstance(x, str)]})
    return out, resp.input_tokens, resp.output_tokens


# ---- enforcement --------------------------------------------------------------

def _strings(v: Any) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [s for x in v for s in _strings(x)]
    if isinstance(v, dict) and "bind" not in v:
        return [s for x in v.values() for s in _strings(x)]
    return []


def _numbers_ok(value: Any, material_text: str) -> bool:
    nums = {n.rstrip(".,") for s in _strings(value) for n in _NUM_RE.findall(s)}
    return all(n in material_text for n in nums if n)


def enforce(raw: list[dict[str, Any]], slots: list[RegionSlot], manifest: ComponentManifest,
            m: Material) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep one region per slot, an allowed component, and props whose numbers
    the material backs. Returns ``(regions, dropped)``."""
    by_name = {s.name: s for s in slots}
    material_text = m.all_text()
    out: list[dict[str, Any]] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for r in raw:
        slot = by_name.get(r.get("id", ""))
        if slot is None or slot.name in seen:
            dropped.append(f"{r.get('id')!r}: not a slot on this page")
            continue
        allowed = {e.id for e in allowed_entries(slot, manifest)}
        if r.get("component") not in allowed:
            dropped.append(f"{slot.name}: component {r.get('component')!r} not allowed here")
            continue
        props = {}
        for k, v in (r.get("props") or {}).items():
            if _numbers_ok(v, material_text):
                props[k] = v
            else:
                dropped.append(f"{slot.name}.{k}: a number not found in the site's content")
        seen.add(slot.name)
        out.append({"id": slot.name, "component": r["component"], "props": props})
    return out, dropped


async def build_plan(
    db: AsyncSession, rt: Any, site_key: str, slots: list[RegionSlot], intent: Intent, sig: Signals, *,
    manifest: ComponentManifest, registry: Any, llm: Any = None, model: Optional[str] = None,
    bindable: str = "", brand_voice: str = "",
) -> dict[str, Any]:
    """``{plan, composer, build_ms, tokens, dropped, problems}``."""
    t0 = time.monotonic()
    bridge = rt.bridge(db, site_key=site_key)
    m = await gather(db, bridge, site_key, intent, sig, threshold=rt.settings.cortex_confidence_threshold)

    def finish(regions: list[dict[str, Any]]) -> Any:
        return validate_plan({"title": intent.label, "regions": regions,
                              "intent": intent.to_dict(),
                              "provenance": {"source": "planner", "manifest": manifest.source,
                                             "manifest_version": manifest.version}},
                             manifest=manifest, catalogue=registry, site_key=site_key)

    composer, tokens, dropped = "rules", (0, 0), []
    report = None
    if llm is not None:
        got = await compose_llm(llm, model, slots, manifest, intent, sig, m,
                                bindable=bindable, brand_voice=brand_voice)
        if got is not None:
            regions, dropped = enforce(got[0], slots, manifest, m)
            report = finish(regions)
            tokens = (got[1], got[2])
            if report.plan.regions:
                composer = "model"
            else:
                report = None
    if report is None:
        regions, more = enforce(compose_rules(slots, manifest, intent, sig, m), slots, manifest, m)
        dropped += more
        report = finish(regions)
    report.plan.provenance["composer"] = composer
    return {"plan": report.plan.to_dict(), "composer": composer, "tokens": list(tokens),
            "build_ms": int((time.monotonic() - t0) * 1000),
            "dropped": dropped + report.dropped, "problems": report.problems}
