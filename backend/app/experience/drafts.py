"""
Draft-manifest generator (P0-9, decision D8).

FluidBuddha writes the first draft of a site's component manifest; the
customer reviews, edits and approves it in the console. Nothing here reaches
the planner until an Admin approves the version (``store.approve_version``).

Two sources:

* **Storybook** — the published Storybook's ``index.json`` (v7+) or
  ``stories.json`` (v6). Each component (story title) becomes a
  ``wc:<tag>`` entry: the customer's own component, drawn from their bundle.
  Props come from ``argTypes`` when the index carries them, or from an
  optional ``react-docgen`` / ``react-docgen-typescript`` JSON the customer
  uploads. Story names become ``use_when`` hints.
* **The live site** — section-level elements whose class or id name a known
  pattern (hero, pricing, faq, testimonials…) are counted across a few pages;
  each pattern seen becomes an entry mapped onto the matching built-in
  renderer, with that renderer's props.

Both return ``{"data": <manifest json>, "notes": str, "found": int}``.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urljoin, urlsplit

from app.experience.manifest import _DEFAULT_PROPS, valid_tag

# ---- shared helpers ---------------------------------------------------------

_WORD_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")

# Built-in renderer for a component/section name, by keyword (first match wins).
_RENDERER_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("hero", "jumbotron", "masthead"), "hero"),
    (("pricing", "price", "plans", "tier"), "pricing_table"),
    (("faq", "questions", "accordion"), "faq"),
    (("testimonial", "quote", "review"), "testimonials"),
    (("logo", "clients", "partners", "customers"), "logos"),
    (("compare", "comparison", "versus"), "comparison"),
    (("feature", "benefit", "services"), "feature_grid"),
    (("cta", "calltoaction", "call-to-action", "signup-banner"), "cta"),
    (("chart", "graph", "stats"), "chart"),
    (("contact", "enquiry", "inquiry", "form", "newsletter"), "enquiry_form"),
    (("roi", "calculator", "savings"), "roi_calculator"),
    (("steps", "process", "how-it-works", "workflow", "timeline"), "flowchart"),
    (("gallery", "media", "video", "image", "banner"), "media"),
]

_TEXT_PROPS = {"title", "heading", "headline", "subtitle", "subheading", "label", "body",
               "description", "caption", "text", "eyebrow", "tagline", "cta", "ctalabel",
               "buttonlabel", "buttontext"}


def words(name: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(name.replace("-", " ").replace("_", " "))]


def pascal(name: str) -> str:
    return "".join(w.capitalize() for w in words(name)) or "Component"


def kebab(name: str) -> str:
    return "-".join(words(name))


def id_prefix(site_key: str) -> str:
    p = re.sub(r"[^a-z0-9]", "", site_key.lower())
    return p if p and p[0].isalpha() else f"site{p}"


def guess_renderer(name: str) -> Optional[str]:
    low = name.lower()
    flat = low.replace("-", "").replace("_", "").replace(" ", "")
    for keys, renderer in _RENDERER_HINTS:
        if any(k.replace("-", "") in flat for k in keys):
            return renderer
    return None


def _tag_for(prefix: str, name: str) -> str:
    tag = f"{prefix}-{kebab(name)}"
    return tag if valid_tag(tag) else f"{prefix}-component-{kebab(name) or 'x'}"


def _source_for(prop: str, ptype: str) -> str:
    if ptype == "string" and prop.lower().replace("_", "") in _TEXT_PROPS:
        return "model_text"
    return "either"


# ---- Storybook --------------------------------------------------------------

def _argtype_spec(arg: Any) -> Optional[dict[str, Any]]:
    """Storybook argType → manifest prop spec."""
    if not isinstance(arg, dict):
        return None
    t = arg.get("type")
    tname = (t.get("name") if isinstance(t, dict) else t) or ""
    control = arg.get("control")
    cname = (control.get("type") if isinstance(control, dict) else control) or ""
    options = arg.get("options") or (t.get("value") if isinstance(t, dict) and tname == "enum" else None)
    spec: dict[str, Any] = {}
    if tname in ("string", "text") or cname in ("text", "color", "date"):
        spec["type"] = "string"
    elif tname == "number" or cname in ("number", "range"):
        spec["type"] = "number"
    elif tname == "boolean" or cname == "boolean":
        spec["type"] = "boolean"
    elif tname in ("array",) or cname == "array":
        spec["type"] = "array"
    elif tname in ("object",) or cname == "object":
        spec["type"] = "object"
    elif tname == "enum" or cname in ("select", "radio", "inline-radio"):
        spec["type"] = "string"
    elif tname == "function" or cname == "action":
        return None  # callbacks are not data
    else:
        spec["type"] = "any"
    if isinstance(options, list) and options and all(isinstance(o, (str, int)) for o in options):
        spec["enum"] = [str(o) for o in options][:20]
    if isinstance(t, dict) and t.get("required"):
        spec["required"] = True
    return spec


def _docgen_type(prop: dict[str, Any]) -> str:
    t = prop.get("tsType") or prop.get("flowType") or prop.get("type") or {}
    name = str((t.get("name") if isinstance(t, dict) else t) or "").lower()
    raw = str((t.get("raw") if isinstance(t, dict) else "") or "")
    if name in ("func", "function") or "=>" in raw:
        return "function"
    if name in ("string",):
        return "string"
    if name in ("number",):
        return "number"
    if name in ("bool", "boolean"):
        return "boolean"
    if name in ("array", "arrayof") or name.endswith("[]") or raw.endswith("[]") or name.startswith("array<"):
        return "array"
    if name in ("object", "shape", "signature", "objectof") or name.startswith("{"):
        return "object"
    if name in ("enum", "union"):
        return "string"
    return "any"


def _docgen_index(docgen: Any) -> dict[str, dict[str, Any]]:
    """react-docgen / react-docgen-typescript output → {ComponentName: props}."""
    out: dict[str, dict[str, Any]] = {}
    items: list[Any]
    if isinstance(docgen, list):
        items = docgen
    elif isinstance(docgen, dict):
        items = []
        for v in docgen.values():  # {file: [components]} or {file: component}
            items.extend(v if isinstance(v, list) else [v])
    else:
        items = []
    for comp in items:
        if not isinstance(comp, dict):
            continue
        name = str(comp.get("displayName") or "").strip()
        props = comp.get("props")
        if not name or not isinstance(props, dict):
            continue
        specs: dict[str, Any] = {}
        for pname, p in list(props.items())[:40]:
            if not isinstance(p, dict):
                continue
            ptype = _docgen_type(p)
            if ptype == "function" or pname in ("children", "className", "style"):
                continue
            spec: dict[str, Any] = {"type": ptype, "source": _source_for(pname, ptype)}
            if p.get("required"):
                spec["required"] = True
            specs[pname] = spec
        out[name] = specs
    return out


def draft_from_storybook(
    index: Any, *, site_key: str, docgen: Any = None,
) -> dict[str, Any]:
    index = index if isinstance(index, dict) else {}
    raw_entries = index.get("entries") or index.get("stories") or {}
    if isinstance(raw_entries, list):
        raw_entries = {str(i): e for i, e in enumerate(raw_entries)}
    by_title: dict[str, dict[str, Any]] = {}
    for e in raw_entries.values() if isinstance(raw_entries, dict) else []:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "docs" or (e.get("parameters") or {}).get("docsOnly"):
            continue
        title = str(e.get("title") or e.get("kind") or "").strip()
        if not title:
            continue
        slot = by_title.setdefault(title, {"stories": [], "argTypes": {}})
        if e.get("name"):
            slot["stories"].append(str(e["name"]))
        arg_types = e.get("argTypes") or (e.get("parameters") or {}).get("argTypes")
        if isinstance(arg_types, dict):
            slot["argTypes"].update(arg_types)

    docs = _docgen_index(docgen)
    prefix = id_prefix(site_key)
    components: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    without_props: list[str] = []
    for title, info in sorted(by_title.items()):
        name = title.rsplit("/", 1)[-1]
        cid = f"{prefix}.{pascal(name)}"
        if cid in used_ids:
            continue
        used_ids.add(cid)
        props: dict[str, Any] = {}
        for pname, arg in list(info["argTypes"].items())[:40]:
            spec = _argtype_spec(arg)
            if spec is not None:
                spec.setdefault("source", _source_for(pname, spec["type"]))
                props[pname] = spec
        if not props:
            props = dict(docs.get(pascal(name)) or docs.get(name) or {})
        if not props:
            without_props.append(cid)
        renderer_hint = guess_renderer(name)
        components.append({
            "id": cid,
            "renderer": f"wc:{_tag_for(prefix, name)}",
            "purpose": (f"{name} from Storybook ({title})"
                        + (f"; looks like a {renderer_hint.replace('_', ' ')}" if renderer_hint else "")),
            "use_when": [kebab(s) for s in info["stories"]][:10],
            "props": props,
        })

    notes = [f"Generated from Storybook: {len(components)} component(s)."]
    if components:
        notes.append("Add the bundle (the https URL of the script that defines these "
                     "elements, with its sha384 integrity hash) before approving.")
        notes.append("Each Web Component must be built as a custom element with the tag "
                     "shown (the FluidBuddha React adapter does this).")
    if without_props:
        notes.append(f"No props found for {len(without_props)} component(s); add them, or "
                     "upload a react-docgen JSON next time.")
    return {
        "data": {"include_defaults": True, "components": components},
        "notes": " ".join(notes),
        "found": len(components),
    }


# ---- live site --------------------------------------------------------------

_SECTION_TAGS = {"section", "header", "footer", "aside", "article", "div", "form"}


class _SectionReader(HTMLParser):
    """Collects class/id tokens of section-level elements, nesting-agnostic."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"] or "")
        if tag not in _SECTION_TAGS:
            return
        names = " ".join(filter(None, [a.get("id"), a.get("class"), a.get("data-section"),
                                       a.get("aria-label")]))
        if names:
            self.tokens.append(names)


def sections_in_html(html: str) -> list[tuple[str, str]]:
    """``[(renderer, token)]`` for each section-level element naming a pattern."""
    r = _SectionReader()
    try:
        r.feed(html)
    except Exception:  # malformed HTML: keep what was read
        pass
    out: list[tuple[str, str]] = []
    for names in r.tokens:
        for token in re.split(r"\s+", names):
            renderer = guess_renderer(token)
            if renderer and len(token) <= 60:
                out.append((renderer, token))
                break
    return out


def draft_from_pages(pages: list[tuple[str, str]], *, site_key: str) -> dict[str, Any]:
    """``pages`` = ``[(url, html)]`` → a draft over the built-in renderers."""
    seen_on: dict[str, set[str]] = defaultdict(set)
    tokens: dict[str, Counter] = defaultdict(Counter)
    for url, html in pages:
        path = urlsplit(url).path or "/"
        for renderer, token in sections_in_html(html):
            seen_on[renderer].add(path)
            tokens[renderer][token.lower()] += 1

    prefix = id_prefix(site_key)
    components: list[dict[str, Any]] = []
    for renderer, paths in sorted(seen_on.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        token = tokens[renderer].most_common(1)[0][0]
        name = pascal(token) if len(words(token)) <= 4 else pascal(renderer)
        cid = f"{prefix}.{name}"
        if any(c["id"] == cid for c in components):
            cid = f"{prefix}.{pascal(renderer)}"
        props = {k: v.to_dict() for k, v in _DEFAULT_PROPS.get(renderer, {}).items()}
        components.append({
            "id": cid,
            "renderer": renderer,
            "purpose": (f"Matches the site's '{token}' sections "
                        f"(seen on {len(paths)} page{'s' if len(paths) != 1 else ''})"),
            "use_when": sorted(p.strip("/").replace("/", "-") or "home" for p in paths)[:10],
            "props": props,
        })
    notes = (f"Generated from {len(pages)} page(s) of the live site: "
             f"{len(components)} section pattern(s), drawn with FluidBuddha's built-in "
             "renderers in your brand's design tokens. Rename, edit or remove entries "
             "before approving.")
    return {
        "data": {"include_defaults": True, "components": components},
        "notes": notes,
        "found": len(components),
    }


# ---- fetching (SSRF-safe; injectable for tests) ------------------------------

Fetch = Callable[..., Awaitable[Any]]
_JSON_TYPES = ("application/json", "text/json")
_HTML_TYPES = ("text/html", "application/xhtml+xml")
MAX_SITE_PAGES = 8


async def fetch_storybook_index(base_url: str, fetch: Fetch) -> dict[str, Any]:
    """Fetch ``index.json`` (Storybook 7+), else ``stories.json`` (v6)."""
    base = base_url.strip()
    if base.endswith((".json",)):
        candidates = [base]
    else:
        base = base.rstrip("/") + "/"
        candidates = [urljoin(base, "index.json"), urljoin(base, "stories.json")]
    last: Exception | None = None
    for url in candidates:
        try:
            got = await fetch(url, allowed_types=_JSON_TYPES, max_bytes=10_000_000)
            data = json.loads(got.text)
            if isinstance(data, dict) and (data.get("entries") or data.get("stories")):
                return data
        except Exception as exc:  # try the next candidate
            last = exc
    raise ValueError(f"No Storybook index found at {base_url}" + (f" ({last})" if last else ""))


async def fetch_site_pages(
    start_url: str, fetch: Fetch, max_pages: int = 5,
) -> list[tuple[str, str]]:
    """The start page plus same-host links from it, up to ``max_pages``."""
    max_pages = max(1, min(max_pages, MAX_SITE_PAGES))
    first = await fetch(start_url, allowed_types=_HTML_TYPES)
    pages = [(first.url, first.text)]
    host = urlsplit(first.url).netloc
    reader = _SectionReader()
    try:
        reader.feed(first.text)
    except Exception:
        pass
    queue: list[str] = []
    for href in reader.links:
        u = urljoin(first.url, href).split("#", 1)[0]
        p = urlsplit(u)
        if p.scheme in ("http", "https") and p.netloc == host and u not in queue and u != first.url:
            queue.append(u)
    for u in queue[: max_pages - 1]:
        try:
            got = await fetch(u, allowed_types=_HTML_TYPES)
            pages.append((got.url, got.text))
        except Exception:  # skip pages that fail
            continue
    return pages
