"""
Server-side rendering of composed pages (P2-1).

Renders a bound plan to semantic HTML that reads well without JavaScript (for
visitors on slow devices and for crawlers), using the same ``fbpage-*``
classes as the widget so patches and hydration address the same structure:

* every region is a ``<section data-fb-region data-fb-component data-fb-state>``;
* interactive sections (charts, ROI calculators, enquiry forms) render a
  readable fallback and are marked ``data-fb-hydrate``; their props travel in
  ``<script type="application/json" id="fb-page-data">`` and
  ``fluid-buddha-composed.global.js`` takes them over;
* a customer Web Component renders as its custom element with a **declarative
  shadow root** holding a readable fallback; the element replaces it when it
  upgrades.

Everything model- or data-supplied is escaped; URLs must be https.
"""
from __future__ import annotations

import json
import re
from html import escape
from typing import Any, Optional

from app.design.system import DesignSystem

INTERACTIVE = {"chart", "roi_calculator", "enquiry_form"}
_TAG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$")


def _t(v: Any) -> str:
    return escape(str(v)) if v not in (None, "") else ""


def _https(v: Any) -> str:
    s = str(v or "")
    return escape(s) if s.startswith("https://") else ""


def _items(v: Any) -> list[dict[str, Any]]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _h(tag: str, v: Any, cls: str = "") -> str:
    t = _t(v)
    return f'<{tag}{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{t}</{tag}>' if t else ""


def _btn(label: Any, action: Any = None) -> str:
    if not label:
        return ""
    act = f' data-fb-action="{_t(action)}"' if action else ""
    return f'<a class="fbpage-btn" href="#enquiry"{act}>{_t(label)}</a>'


def _readable(props: dict[str, Any]) -> str:
    """A text rendering of arbitrary props (WC fallbacks)."""
    out = []
    for k, v in props.items():
        if isinstance(v, str):
            out.append(f"<p>{_t(v)}</p>")
        elif isinstance(v, list):
            lis = []
            for it in v[:24]:
                if isinstance(it, dict):
                    lis.append("<li>" + " · ".join(_t(x) for x in it.values() if isinstance(x, (str, int, float))) + "</li>")
                elif isinstance(it, (str, int, float)):
                    lis.append(f"<li>{_t(it)}</li>")
            if lis:
                out.append(f"<ul>{''.join(lis)}</ul>")
    return "".join(out)


def section_inner(t: str, p: dict[str, Any], form_action: str = "") -> str:
    if t == "hero":
        return (_h("h1", p.get("title"), "fbpage-hero-title") + _h("p", p.get("subtitle"), "fbpage-hero-sub")
                + _btn(p.get("cta_label"), p.get("action")))
    if t == "text":
        return _h("h2", p.get("title"), "fbpage-h2") + _h("p", p.get("body"), "fbpage-body")
    if t == "cta":
        return (_h("h2", p.get("title"), "fbpage-h2") + _h("p", p.get("body"), "fbpage-body")
                + _btn(p.get("cta_label"), p.get("action")))
    if t == "feature_grid":
        cards = "".join(f'<div class="fbpage-card">{_h("h3", i.get("title"), "fbpage-card-title")}{_h("p", i.get("body"))}</div>'
                        for i in _items(p.get("items")))
        return _h("h2", p.get("title"), "fbpage-h2") + f'<div class="fbpage-grid">{cards}</div>'
    if t == "pricing_table":
        cards = "".join(
            f'<div class="fbpage-card fbpage-tier">{_h("h3", i.get("name"), "fbpage-card-title")}'
            f'{_h("div", i.get("price"), "fbpage-price")}<ul class="fbpage-features">'
            f'{"".join(f"<li>{_t(f)}</li>" for f in (i.get("features") or []) if isinstance(f, (str, int, float)))}</ul></div>'
            for i in _items(p.get("tiers")))
        return _h("h2", p.get("title"), "fbpage-h2") + f'<div class="fbpage-grid">{cards}</div>'
    if t == "faq":
        qa = "".join(f'<details class="fbpage-qa"{" open" if n == 0 else ""}><summary>{_t(i.get("q"))}</summary>'
                     f'<p>{_t(i.get("a"))}</p></details>' for n, i in enumerate(_items(p.get("items"))))
        return _h("h2", p.get("title"), "fbpage-h2") + qa
    if t == "testimonials":
        qs = "".join(f'<figure class="fbpage-card fbpage-quote"><blockquote>{_t(i.get("quote"))}</blockquote>'
                     f'<figcaption>{_t(i.get("name"))}{", " + _t(i.get("role")) if i.get("role") else ""}</figcaption></figure>'
                     for i in _items(p.get("items")))
        return _h("h2", p.get("title"), "fbpage-h2") + f'<div class="fbpage-grid">{qs}</div>'
    if t == "logos":
        imgs = "".join(f'<img src="{_https(i.get("src"))}" alt="{_t(i.get("alt"))}" loading="lazy">'
                       for i in _items(p.get("items")) if _https(i.get("src")))
        return _h("h2", p.get("title"), "fbpage-h2") + f'<div class="fbpage-logos">{imgs}</div>'
    if t == "comparison":
        head = "".join(f"<th>{_t(c)}</th>" for c in (p.get("columns") or []))
        rows = "".join(f"<tr><th>{_t(r.get('label'))}</th>{''.join(f'<td>{_t(v)}</td>' for v in (r.get('values') or []))}</tr>"
                       for r in _items(p.get("rows")))
        return (_h("h2", p.get("title"), "fbpage-h2") +
                f'<div class="fbpage-scroll"><table class="fbpage-table"><thead><tr><th></th>{head}</tr></thead>'
                f"<tbody>{rows}</tbody></table></div>")
    if t == "media":
        src = _https(p.get("src"))
        return ((f'<img class="fbpage-media" src="{src}" alt="{_t(p.get("alt"))}" loading="lazy">' if src else "")
                + _h("p", p.get("caption"), "fbpage-caption"))
    if t == "flowchart":
        steps = "".join(f"<li>{_t(n.get('label'))}</li>" for n in _items(p.get("nodes")))
        return f'<ol class="fbpage-steps">{steps}</ol>'
    if t == "chart":
        rows = "".join(f"<tr><th>{_t(d.get('label'))}</th><td>{_t(d.get('value'))}{(' ' + _t(p.get('unit'))) if p.get('unit') else ''}</td></tr>"
                       for d in _items(p.get("data")))
        return _h("h2", p.get("title"), "fbpage-h2") + f'<table class="fbpage-table">{rows}</table>'
    if t == "roi_calculator":
        return _h("h2", p.get("title") or "Estimate your return", "fbpage-h2") + \
            '<p class="fbpage-body">The calculator loads with the page.</p>'
    if t == "enquiry_form":
        fields = []
        for f in _items(p.get("fields"))[:10]:
            name = re.sub(r"[^a-z0-9_]", "", str(f.get("name") or "").lower())[:40]
            if not name:
                continue
            ftype = f.get("type") if f.get("type") in ("text", "email", "tel", "textarea") else "text"
            label = _t(f.get("label") or name)
            ctrl = (f'<textarea name="{name}" rows="4"></textarea>' if ftype == "textarea"
                    else f'<input name="{name}" type="{ftype}">')
            fields.append(f"<label>{label}{ctrl}</label>")
        # Without JavaScript the form posts to the server's form endpoint (never a
        # GET: personal details must not land in a URL); the hydrate script
        # sends it with fetch instead.
        action = f' action="{_t(form_action)}"' if form_action else ""
        op = re.sub(r"[^A-Za-z0-9_.-]", "", str(p.get("operation_id") or ""))[:80]
        hidden = f'<input type="hidden" name="_operation" value="{op}">' if op else ""
        return (_h("h2", p.get("title"), "fbpage-h2") + f'<form class="fbpage-form" id="enquiry" method="post"{action}>'
                f'{hidden}{"".join(fields)}<button class="fbpage-btn" type="submit">'
                f'{_t(p.get("submit_label") or "Send")}</button></form>')
    return ""


def render_section(s: dict[str, Any], form_action: str = "", step: str = "") -> str:
    t, p = str(s.get("type") or ""), s.get("props") or {}
    attrs = (f'data-fb-region="{_t(s.get("id"))}" data-fb-component="{_t(s.get("component"))}" '
             f'data-fb-state="{_t(s.get("state") or "ready")}"')
    if step:  # a step of a multi-step flow (Phase 4): every step renders; the script shows one at a time
        attrs += f' data-fb-step="{_t(step)}"'
    if s.get("width") == "half":
        attrs += ' data-fb-width="half"'
    if t.startswith("wc:"):
        tag = t[3:]
        if not _TAG_RE.match(tag) or tag.startswith(("fluid-buddha", "fb-")):
            return ""
        props_json = escape(json.dumps(p, ensure_ascii=False, separators=(",", ":")), quote=True)
        return (f'<section class="fbpage-section fbpage-wc" {attrs}><{tag} data-fb-props="{props_json}">'
                f'<template shadowrootmode="open"><div class="fb-fallback">{_readable(p)}</div></template>'
                f"</{tag}></section>")
    inner = section_inner(t, p, form_action)
    if not inner:
        return ""
    hydrate = ' data-fb-hydrate=""' if t in INTERACTIVE else ""
    return f'<section class="fbpage-section fbpage-{_t(t)}" {attrs}{hydrate}>{inner}</section>'


def stylesheet(design: DesignSystem, overrides: Optional[dict[str, str]] = None) -> str:
    """The page stylesheet in the brand's tokens, with the visitor's tunables
    (density, motion, scheme — only where the brand allows them, P3-3)."""
    merged = {**design.to_tokens(), **(overrides or {})}
    tokens = ";".join(f"{k}:{v}" for k, v in merged.items()
                      if re.fullmatch(r"--[a-z0-9-]{1,40}", k) and re.fullmatch(r"[#\w\s.,%()'\"-]{1,200}", str(v)))
    return f""":root{{{tokens}}}
.fbpage-root{{background:var(--ds-color-background,#0c0b09);color:var(--ds-color-text,#f3f5f7);font-family:var(--ds-font,ui-sans-serif,system-ui,sans-serif);font-size:var(--ds-base-size,16px);line-height:1.6}}
.fbpage-inner{{max-width:1000px;margin:0 auto;padding:8px 5vw 96px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ds-gap,34px)}}
.fbpage-inner > *{{grid-column:1 / -1}} .fbpage-inner > [data-fb-width="half"]{{grid-column:auto}}
@media (max-width:720px){{.fbpage-inner > [data-fb-width="half"]{{grid-column:1 / -1}}}}
.fb-steps{{display:flex;gap:10px;flex-wrap:wrap;list-style:none;padding:0;margin:0;font-size:.9rem}}
.fb-steps li{{padding:6px 12px;border-radius:999px;border:1px solid rgba(127,127,127,.35)}}
.fb-steps li[aria-current="step"]{{background:var(--ds-color-primary,#c9a24a);color:var(--ds-color-background,#0c0b09)}}
.fb-step-nav{{display:flex;gap:10px;justify-content:space-between}}
.fbpage-inner > [hidden]{{display:none !important}} .fb-step-nav .fbpage-btn-secondary{{background:transparent;color:inherit;border:1px solid rgba(127,127,127,.45)}}
.fbpage-h2{{font-size:1.6rem;font-family:var(--ds-font-heading,inherit);margin:0 0 12px}}
.fbpage-body{{opacity:.92;max-width:70ch}}
.fbpage-hero{{text-align:center;padding:56px 0 28px}}
.fbpage-hero-title{{font-size:clamp(2rem,5vw,3.4rem);margin:0 0 16px;font-family:var(--ds-font-heading,inherit);color:var(--ds-color-primary,#c9a24a)}}
.fbpage-hero-sub{{font-size:1.15rem;opacity:.85;max-width:60ch;margin:0 auto 24px}}
.fbpage-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:calc(var(--ds-gap,34px) / 2)}}
.fbpage-card{{background:var(--ds-color-surface,#14161c);border-radius:var(--ds-radius,14px);padding:var(--ds-pad,20px);margin:0}}
.fbpage-card-title{{margin:0 0 8px;font-size:1.1rem}}
.fbpage-price{{font-size:1.7rem;font-weight:700;color:var(--ds-color-primary,#c9a24a);margin:6px 0 10px}}
.fbpage-btn{{display:inline-block;background:var(--ds-color-primary,#c9a24a);color:var(--ds-color-background,#0c0b09);border:0;border-radius:var(--ds-radius,14px);padding:12px 22px;font-weight:600;text-decoration:none;cursor:pointer}}
.fbpage-qa{{border-bottom:1px solid rgba(127,127,127,.25);padding:12px 0}} .fbpage-qa summary{{cursor:pointer;font-weight:600}}
.fbpage-table{{border-collapse:collapse;width:100%}} .fbpage-table th,.fbpage-table td{{border-bottom:1px solid rgba(127,127,127,.25);padding:8px 10px;text-align:left}}
.fbpage-scroll{{overflow-x:auto}} .fbpage-logos{{display:flex;flex-wrap:wrap;gap:24px;align-items:center}} .fbpage-logos img{{height:36px}}
.fbpage-media{{max-width:100%;border-radius:var(--ds-radius,14px)}} .fbpage-steps{{display:grid;gap:8px}}
.fbpage-form{{display:grid;gap:12px;max-width:520px}} .fbpage-form label{{display:grid;gap:4px}}
.fbpage-form input,.fbpage-form textarea{{font:inherit;padding:10px;border-radius:8px;border:1px solid rgba(127,127,127,.4);background:transparent;color:inherit}}
.fb-why{{font-size:.8rem;opacity:.7;margin:0 0 6px}} .fb-why span{{margin-left:6px}} .fb-why button{{font:inherit;background:none;border:0;color:inherit;text-decoration:underline;cursor:pointer;padding:0}}
.fb-patched{{animation:fb-patch var(--ds-anim,.9s) ease}} @keyframes fb-patch{{from{{opacity:.2;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}"""


def page_data_json(data: dict[str, Any]) -> str:
    """JSON safe to embed in a <script> element."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026")


def render_fragment(sections: list[dict[str, Any]], *, plan_id: Optional[str], title: str,
                    form_action: str = "", flow: Optional[list[dict[str, Any]]] = None) -> str:
    step_of = {rid: st["step"] for st in (flow or []) for rid in st.get("regions") or []}
    body = "".join(render_section(s, form_action, step_of.get(str(s.get("id")), "")) for s in sections)
    nav = ""
    if flow:  # an ordered list of the steps (readable without JavaScript; the script turns it into tabs)
        nav = ('<ol class="fb-steps">' + "".join(
            f'<li data-fb-step-nav="{_t(st["step"])}">{_t(st.get("title") or st["step"])}</li>' for st in flow) + "</ol>")
    return (f'<main class="fbpage-root" data-fb-plan="{_t(plan_id)}"><div class="fbpage-inner">'
            f"{nav}{body}</div></main>")


def render_document(*, fragment: str, head: dict[str, Any], css: str, data: dict[str, Any],
                    composed_script: str = "", widget_script: str = "", lang: str = "en") -> str:
    """A full HTML page (the hosted shell, and what the Next.js handler returns)."""
    meta = [f"<title>{_t(head.get('title'))}</title>",
            f'<meta name="description" content="{_t(head.get("description"))}">' if head.get("description") else "",
            f'<link rel="canonical" href="{_t(head.get("canonical"))}">' if head.get("canonical") else "",
            f'<meta name="robots" content="{_t(head.get("robots") or "index, follow")}">']
    if head.get("json_ld"):
        meta.append(f'<script type="application/ld+json">{page_data_json(head["json_ld"])}</script>')
    return ("<!doctype html><html lang=\"" + _t(lang) + "\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width, initial-scale=1">' + "".join(meta) +
            f"<style>{css}</style></head><body style=\"margin:0\">{fragment}"
            f'<script type="application/json" id="fb-page-data">{page_data_json(data)}</script>'
            f"{composed_script}{widget_script}</body></html>")
