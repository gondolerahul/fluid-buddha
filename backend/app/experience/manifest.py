"""
Component manifest (strategy §4.2.2).

The manifest is the only vocabulary an Experience Plan may use: each entry
names a component, what it is for, its props (with a type and a *source rule*)
and which renderer draws it.

Source rules decide who may supply a prop's value:

* ``model_text``   — the model writes it (short copy); bindings are refused;
* ``binding_only`` — it must come from a data binding; the model may not write it;
* ``either``       — a literal value or a binding.

Without configuration the manifest is the built-in default: the 14 section
types the SDK ``PageRenderer`` draws today (``pagegen.SECTION_TYPES``), as
``fb.<type>`` entries. A site may add its own entries::

    {"include_defaults": true,
     "bundle": {"url": "https://cdn.acme.com/fb-components.js", "integrity": "sha384-…"},
     "components": [{"id": "acme.PlanComparison", "renderer": "wc:acme-plan-table",
                     "purpose": "...", "use_when": ["compare_plans"],
                     "props": {"tiers": {"type": "array", "source": "binding_only",
                                         "required": true, "max_items": 4}}}]}

Resolution order (P0-7): the site's **approved** manifest version from the
console (``site_component_manifests``, loaded by ``ensure_manifest``) → a file
from ``<SITE>_COMPONENT_MANIFEST`` (path) or ``COMPONENT_MANIFEST_DIR/<site>.json``
→ the default.

Renderers (P0-8): an entry is drawn either by a built-in section renderer
(``hero``, ``pricing_table``…) or by the customer's own Web Component,
``wc:<custom-element-tag>``. Web Component entries need the manifest's
``bundle`` — the script that defines the elements, loaded by the SDK with
subresource integrity.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.orchestrator.pagegen import SECTION_TYPES

logger = logging.getLogger(__name__)

PROP_TYPES = ("string", "number", "boolean", "array", "object", "any")
SOURCES = ("model_text", "binding_only", "either")
BUILTIN_RENDERERS = frozenset(SECTION_TYPES)
MAX_COMPONENTS = 200

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
# A valid custom-element name; FluidBuddha's own elements are reserved.
_TAG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$")
_RESERVED_TAG_PREFIXES = ("fluid-buddha", "fb-")
_SRI_RE = re.compile(r"^sha(256|384|512)-[A-Za-z0-9+/]+={0,2}$")
_URL_BAD_CHARS = frozenset(" \"'<>\\")


def is_wc_renderer(renderer: str) -> bool:
    return renderer.startswith("wc:")


def valid_tag(tag: str) -> bool:
    return bool(_TAG_RE.match(tag)) and not tag.startswith(_RESERVED_TAG_PREFIXES)


def renderer_ok(renderer: str) -> bool:
    if is_wc_renderer(renderer):
        return valid_tag(renderer[3:])
    return renderer in BUILTIN_RENDERERS


def clean_bundle(raw: Any) -> tuple[dict[str, str] | None, str | None]:
    """``(bundle, problem)``: an https script URL with an SRI hash, or why not."""
    if raw in (None, {}, ""):
        return None, None
    if not isinstance(raw, dict):
        return None, "bundle must be {url, integrity}"
    url = str(raw.get("url") or "").strip()
    integrity = str(raw.get("integrity") or "").strip()
    if not url.startswith("https://") or len(url) > 1000 or any(c in _URL_BAD_CHARS for c in url):
        return None, "bundle.url must be an https:// URL"
    if not _SRI_RE.match(integrity):
        return None, ("bundle.integrity must be a sha256-/sha384-/sha512- hash "
                      "(subresource integrity)")
    return {"url": url, "integrity": integrity}, None


@dataclass(frozen=True)
class PropSpec:
    type: str = "any"
    source: str = "either"
    required: bool = False
    max_items: int | None = None
    max_length: int | None = None
    enum: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: Any) -> "PropSpec":
        d = d if isinstance(d, dict) else {}
        ptype = str(d.get("type") or "any")
        source = str(d.get("source") or "either")
        enum = d.get("enum") or ()
        return cls(
            type=ptype if ptype in PROP_TYPES else "any",
            source=source if source in SOURCES else "either",
            required=bool(d.get("required", False)),
            max_items=_pos_int(d.get("max_items")),
            max_length=_pos_int(d.get("max_length")),
            enum=tuple(str(x) for x in enum) if isinstance(enum, list) else (),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "source": self.source}
        if self.required:
            d["required"] = True
        if self.max_items:
            d["max_items"] = self.max_items
        if self.max_length:
            d["max_length"] = self.max_length
        if self.enum:
            d["enum"] = list(self.enum)
        return d

    def describe(self) -> str:
        bits = [self.type]
        if self.required:
            bits.append("required")
        if self.source != "either":
            bits.append(self.source)
        if self.enum:
            bits.append("|".join(self.enum))
        if self.max_items:
            bits.append(f"≤{self.max_items} items")
        return " ".join(bits)


@dataclass(frozen=True)
class ManifestEntry:
    id: str
    renderer: str
    purpose: str = ""
    props: dict[str, PropSpec] = field(default_factory=dict)
    use_when: tuple[str, ...] = ()
    avoid_when: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    version: int = 1
    ssr: bool = True

    @property
    def short_name(self) -> str:
        return self.id.rsplit(".", 1)[-1]

    def to_prompt(self) -> str:
        props = ", ".join(f"{k} ({v.describe()})" for k, v in self.props.items())
        when = f" Use when: {', '.join(self.use_when)}." if self.use_when else ""
        return f"{self.id} — {self.purpose}{when} props: {props or 'none'}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "renderer": self.renderer, "purpose": self.purpose,
            "use_when": list(self.use_when), "avoid_when": list(self.avoid_when),
            "actions": list(self.actions), "version": self.version, "ssr": self.ssr,
            "props": {k: v.to_dict() for k, v in self.props.items()},
        }


class ComponentManifest:
    def __init__(
        self, entries: list[ManifestEntry], *, bundle: dict[str, str] | None = None,
        source: str = "default", version: int | None = None,
    ) -> None:
        self._entries: dict[str, ManifestEntry] = {}
        for e in entries:
            self._entries[e.id] = e
        self.bundle = bundle
        self.source = source          # default | file | console
        self.version = version        # approved console version, if any

    def get(self, component_id: str) -> ManifestEntry | None:
        return self._entries.get(component_id)

    def entries(self) -> list[ManifestEntry]:
        return list(self._entries.values())

    def ids(self) -> list[str]:
        return list(self._entries)

    def to_prompt(self) -> str:
        lines = "; ".join(e.to_prompt() for e in self._entries.values())
        return (
            "PAGE COMPONENTS — each region of a page uses one of these EXACT "
            "component ids with its props: " + lines + "."
        )


def _pos_int(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _p(ptype: str, source: str = "either", *, required: bool = False,
       max_items: int | None = None, max_length: int | None = None,
       enum: tuple[str, ...] = ()) -> PropSpec:
    return PropSpec(ptype, source, required, max_items, max_length, enum)


_TITLE = _p("string", "model_text", max_length=160)

# Prop specs of the built-in sections (shapes from pagegen.SECTION_TYPES).
# Lists of facts are "either" so a site can bind them to its own API.
_DEFAULT_PROPS: dict[str, dict[str, PropSpec]] = {
    "hero": {"title": _p("string", "model_text", required=True, max_length=160),
             "subtitle": _p("string", "model_text", max_length=300),
             "cta_label": _p("string", "model_text", max_length=40),
             "action": _p("string", "model_text", max_length=40)},
    "feature_grid": {"title": _TITLE,
                     "items": _p("array", required=True, max_items=12)},
    "text": {"title": _TITLE,
             "body": _p("string", "model_text", required=True, max_length=2000)},
    "pricing_table": {"title": _TITLE,
                      "tiers": _p("array", required=True, max_items=6)},
    "chart": {"chart_type": _p("string", "model_text", enum=("bar", "line", "pie")),
              "title": _TITLE, "unit": _p("string", "model_text", max_length=20),
              "data": _p("array", required=True, max_items=48)},
    "flowchart": {"nodes": _p("array", required=True, max_items=24),
                  "edges": _p("array", max_items=48)},
    "enquiry_form": {"title": _TITLE,
                     "fields": _p("array", required=True, max_items=10),
                     "submit_label": _p("string", "model_text", max_length=40),
                     "operation_id": _p("string", "model_text", max_length=80)},
    "cta": {"title": _p("string", "model_text", required=True, max_length=160),
            "body": _p("string", "model_text", max_length=400),
            "cta_label": _p("string", "model_text", required=True, max_length=40),
            "action": _p("string", "model_text", max_length=40)},
    "media": {"src": _p("string", required=True, max_length=500),
              "alt": _p("string", "model_text", max_length=200),
              "caption": _p("string", "model_text", max_length=200)},
    "testimonials": {"title": _TITLE, "items": _p("array", required=True, max_items=8)},
    "logos": {"title": _TITLE, "items": _p("array", required=True, max_items=16)},
    "faq": {"title": _TITLE, "items": _p("array", required=True, max_items=12)},
    "comparison": {"title": _TITLE, "columns": _p("array", required=True, max_items=6),
                   "rows": _p("array", required=True, max_items=24)},
    "roi_calculator": {"title": _TITLE, "seats": _p("number"),
                       "monthly_cost": _p("number"), "hours_saved": _p("number"),
                       "hourly_value": _p("number")},
}


def _purpose(section_type: str) -> str:
    desc = SECTION_TYPES[section_type]
    return desc.split(". props:", 1)[0].strip()


@lru_cache(maxsize=1)
def default_entries() -> tuple[ManifestEntry, ...]:
    return tuple(
        ManifestEntry(
            id=f"fb.{stype}", renderer=stype, purpose=_purpose(stype),
            props=dict(_DEFAULT_PROPS.get(stype, {})),
        )
        for stype in SECTION_TYPES
    )


def default_manifest() -> ComponentManifest:
    return ComponentManifest(list(default_entries()))


def entry_problem(d: Any) -> str | None:
    """Why a customer manifest entry is unusable, or None."""
    if not isinstance(d, dict):
        return "entry is not an object"
    cid = str(d.get("id") or "").strip()
    renderer = str(d.get("renderer") or "").strip()
    if not _ID_RE.match(cid):
        return f"bad id {cid!r} (use a dotted name such as acme.PlanTable)"
    if not renderer_ok(renderer):
        return (f"{cid}: renderer {renderer!r} must be a built-in section "
                f"({', '.join(sorted(BUILTIN_RENDERERS))}) or wc:<custom-element-tag>")
    return None


def entry_from_dict(d: Any) -> ManifestEntry | None:
    """A customer manifest entry, or None (with a log line) if unusable."""
    problem = entry_problem(d)
    if problem:
        logger.warning("manifest entry skipped: %s", problem)
        return None
    cid = str(d.get("id") or "").strip()
    renderer = str(d.get("renderer") or "").strip()
    props_raw = d.get("props") if isinstance(d.get("props"), dict) else {}
    props = {str(k): PropSpec.from_dict(v) for k, v in list(props_raw.items())[:40]}

    def strs(key: str) -> tuple[str, ...]:
        v = d.get(key)
        return tuple(str(x)[:80] for x in v[:20]) if isinstance(v, list) else ()

    return ManifestEntry(
        id=cid, renderer=renderer, purpose=str(d.get("purpose") or "")[:300],
        props=props, use_when=strs("use_when"), avoid_when=strs("avoid_when"),
        actions=strs("actions"), version=_pos_int(d.get("version")) or 1,
        ssr=bool(d.get("ssr", True)),
    )


def parse_manifest(
    data: Any, *, source: str = "file", version: int | None = None,
) -> tuple[ComponentManifest, list[str]]:
    """Build a manifest and list every entry that was refused, and why."""
    problems: list[str] = []
    data = data if isinstance(data, dict) else {}
    bundle, bundle_problem = clean_bundle(data.get("bundle"))
    if bundle_problem:
        problems.append(bundle_problem)
    entries: list[ManifestEntry] = []
    if data.get("include_defaults", True):
        entries.extend(default_entries())
    raw_list = data.get("components") or []
    if not isinstance(raw_list, list):
        problems.append("components must be a list")
        raw_list = []
    seen: set[str] = set()
    for raw in raw_list[:MAX_COMPONENTS]:
        problem = entry_problem(raw)
        if problem:
            problems.append(problem)
            continue
        e = entry_from_dict(raw)
        if e is None:
            continue
        if e.id in seen:
            problems.append(f"{e.id}: duplicate id")
            continue
        if is_wc_renderer(e.renderer) and bundle is None:
            problems.append(f"{e.id}: a Web Component needs the manifest's bundle {{url, integrity}}")
            continue
        seen.add(e.id)
        entries.append(e)
    if len(raw_list) > MAX_COMPONENTS:
        problems.append(f"only the first {MAX_COMPONENTS} components are used")
    return ComponentManifest(entries, bundle=bundle, source=source, version=version), problems


def manifest_from_dict(data: Any) -> ComponentManifest:
    return parse_manifest(data)[0]


def _env_key(site_key: str) -> str:
    return site_key.upper().replace("-", "_")


def _manifest_path(site_key: str) -> Path | None:
    override = os.getenv(f"{_env_key(site_key)}_COMPONENT_MANIFEST")
    if override:
        return Path(override)
    base = os.getenv("COMPONENT_MANIFEST_DIR")
    if base:
        p = Path(base) / f"{site_key}.json"
        if p.exists():
            return p
    return None


@lru_cache(maxsize=32)
def _file_manifest(site_key: str) -> ComponentManifest | None:
    path = _manifest_path(site_key)
    if not (path and path.exists()):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("loaded component manifest for %s from %s", site_key, path)
    except Exception as exc:  # a malformed file must not break the stack
        logger.warning("failed to read component manifest %s: %s", path, exc)
        return None
    return parse_manifest(data, source="file")[0]


_TTL_S = 30.0
# Approved console manifests by site: (expires_at, manifest or None).
_approved: dict[str, tuple[float, ComponentManifest | None]] = {}


def remember_approved(site_key: str, data: dict[str, Any] | None, version: int | None) -> None:
    manifest = (parse_manifest(data, source="console", version=version)[0]
                if data is not None else None)
    _approved[site_key] = (time.monotonic() + _TTL_S, manifest)


def forget(site_key: str) -> None:
    """Drop cached manifests for a site (after an approval)."""
    _approved.pop(site_key, None)
    _file_manifest.cache_clear()


def clear_manifest_cache() -> None:
    _approved.clear()
    _file_manifest.cache_clear()


async def ensure_manifest(site_key: str) -> None:
    """Load the site's approved console manifest into the cache unless fresh.
    Called at request entry points, like ``ensure_design``."""
    hit = _approved.get(site_key)
    if hit and hit[0] > time.monotonic():
        return
    from app.db import session_scope
    from app.experience import store

    try:
        async with session_scope() as db:
            row = await store.approved_manifest(db, site_key)
    except Exception as exc:  # never let a manifest read break a conversation
        logger.warning("manifest load failed for %s: %s", site_key, exc)
        if hit:
            _approved[site_key] = (time.monotonic() + _TTL_S, hit[1])
        return
    remember_approved(site_key, row["data"] if row else None, row["version"] if row else None)


def load_manifest(site_key: str) -> ComponentManifest:
    """Approved console version → file → built-in default."""
    hit = _approved.get(site_key)
    if hit and hit[1] is not None:
        return hit[1]
    return _file_manifest(site_key) or default_manifest()
