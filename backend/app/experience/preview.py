"""
Script-free HTML preview of generated regions for the console (P1-4).

The console shows it in a sandboxed iframe (``srcdoc``, no scripts), so this
renders the built-in section types as plain HTML in the site's design tokens.
A customer Web Component (``wc:<tag>``) is shown as a labelled box with its
props, since its code isn't run in the console.
"""
from __future__ import annotations

import json
import re
from html import escape
from typing import Any

from app.design.system import DesignSystem

_COLOR = re.compile(r"^#[0-9a-fA-F]{3,6}$")
_FONT = re.compile(r"^[\w\s,'\"-]{1,200}$")


def _c(v: Any, default: str) -> str:
    return v if isinstance(v, str) and _COLOR.match(v) else default


def _t(v: Any) -> str:
    return escape(str(v)) if v not in (None, "") else ""


def _items(v: Any) -> list[dict[str, Any]]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def section_html(name: str, s: dict[str, Any]) -> str:
    t, p = s.get("type", ""), s.get("props") or {}
    body = ""
    if t == "hero":
        body = f"<h1>{_t(p.get('title'))}</h1><p class=lead>{_t(p.get('subtitle'))}</p>" + \
            (f"<span class=btn>{_t(p.get('cta_label'))}</span>" if p.get("cta_label") else "")
    elif t == "text":
        body = (f"<h2>{_t(p.get('title'))}</h2>" if p.get("title") else "") + f"<p>{_t(p.get('body'))}</p>"
    elif t == "cta":
        body = f"<h2>{_t(p.get('title'))}</h2><p>{_t(p.get('body'))}</p><span class=btn>{_t(p.get('cta_label'))}</span>"
    elif t == "feature_grid":
        cards = "".join(f"<div class=card><h3>{_t(i.get('title'))}</h3><p>{_t(i.get('body'))}</p></div>"
                        for i in _items(p.get("items")))
        body = f"<h2>{_t(p.get('title'))}</h2><div class=grid>{cards}</div>"
    elif t == "pricing_table":
        cards = "".join(
            f"<div class=card><h3>{_t(i.get('name'))}</h3><div class=price>{_t(i.get('price'))}</div>"
            f"<ul>{''.join(f'<li>{_t(f)}</li>' for f in (i.get('features') or []) if isinstance(f, str))}</ul></div>"
            for i in _items(p.get("tiers")))
        body = f"<h2>{_t(p.get('title'))}</h2><div class=grid>{cards}</div>"
    elif t == "faq":
        qa = "".join(f"<details open><summary>{_t(i.get('q'))}</summary><p>{_t(i.get('a'))}</p></details>"
                     for i in _items(p.get("items")))
        body = f"<h2>{_t(p.get('title'))}</h2>{qa}"
    elif t == "testimonials":
        qs = "".join(f"<figure class=card><blockquote>{_t(i.get('quote'))}</blockquote>"
                     f"<figcaption>{_t(i.get('name'))}</figcaption></figure>" for i in _items(p.get("items")))
        body = f"<h2>{_t(p.get('title'))}</h2><div class=grid>{qs}</div>"
    elif t == "comparison":
        head = "".join(f"<th>{_t(c)}</th>" for c in (p.get("columns") or []))
        rows = "".join(f"<tr><th>{_t(r.get('label'))}</th>{''.join(f'<td>{_t(v)}</td>' for v in (r.get('values') or []))}</tr>"
                       for r in _items(p.get("rows")))
        body = f"<h2>{_t(p.get('title'))}</h2><table><tr><th></th>{head}</tr>{rows}</table>"
    else:
        label = t[3:] if t.startswith("wc:") else t
        body = (f"<div class=wc>Drawn by <code>&lt;{_t(label)}&gt;</code> on your site</div>"
                f"<pre>{_t(json.dumps(p, ensure_ascii=False, indent=2)[:2000])}</pre>")
    return (f"<section data-region='{_t(name)}'><div class=tag>{_t(name)} · {_t(s.get('component'))}</div>"
            f"{body}</section>")


def render_preview(regions: dict[str, dict[str, Any]], design: DesignSystem, *, title: str = "") -> str:
    c = design.colors
    bg, surface = _c(c.get("background"), "#0c0b09"), _c(c.get("surface"), "#14161c")
    text_, muted, primary = _c(c.get("text"), "#f3f5f7"), _c(c.get("muted"), "#9aa3b2"), _c(c.get("primary"), "#c9a24a")
    font = design.typography.get("font_family") or ""
    font = font if _FONT.match(str(font)) else "ui-sans-serif, system-ui, sans-serif"
    radius = design.radius if re.fullmatch(r"\d{1,3}(px|rem|em|%)", design.radius or "") else "14px"
    sections = "".join(section_html(n, s) for n, s in regions.items()) or \
        "<p class=empty>Nothing to show: no region could be filled from the site's content.</p>"
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src https: data:">
<title>{_t(title)}</title><style>
body{{margin:0;padding:24px;background:{bg};color:{text_};font-family:{font};line-height:1.55}}
section{{border:1px dashed {muted}55;border-radius:{radius};padding:20px;margin-bottom:18px;position:relative}}
.tag{{position:absolute;top:-10px;left:12px;background:{bg};color:{muted};font:12px ui-monospace,monospace;padding:0 6px}}
h1{{color:{primary};margin:0 0 8px}} h2{{margin:0 0 10px}} .lead{{color:{muted}}}
.btn{{display:inline-block;background:{primary};color:{bg};border-radius:{radius};padding:8px 14px;font-weight:600}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.card{{background:{surface};border-radius:{radius};padding:14px;margin:0}} .price{{color:{primary};font-weight:700}}
table{{border-collapse:collapse}} td,th{{border:1px solid {muted}44;padding:6px 10px;text-align:left}}
.wc{{color:{muted}}} pre{{white-space:pre-wrap;font-size:12px;color:{muted}}} .empty{{color:{muted}}}
</style></head><body>{sections}</body></html>"""
