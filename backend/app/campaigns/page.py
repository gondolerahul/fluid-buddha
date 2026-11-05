"""
The hosted landing page (M3-1): server-rendered from the composed spec, so it
reads (and paints its largest content) without waiting for any script. Themed
with the site's design tokens, every value escaped.

Scripts, all from our own origins and loaded ``defer``/``async``:

* the site's widget (``/widget/loader.js`` with the site's key), so the agent
  is on the page;
* ``fluid-buddha-page.global.js``, which draws the interactive sections
  (ROI calculator, charts) from a JSON block and reports engagement.

The enquiry form is a plain HTML form posted to the page's own ``/lead``
route; the call to action goes through ``/go`` so the click counts.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit

from app.design.system import DesignSystem
from app.recaps.page import _FONT, _SIZE, _color, sdk_origin

_SLOTTED = {"roi_calculator": "roi_calculator", "chart": "chart"}


def _origin(url: str) -> str:
    u = urlsplit(url or "")
    return f"{u.scheme}://{u.netloc}" if u.scheme in ("http", "https") and u.netloc else ""


def csp(*, api_base: str, sdk_base: str, frame_ancestors: list[str]) -> str:
    api = _origin(api_base)
    ws = api.replace("https://", "wss://").replace("http://", "ws://")
    sdk = sdk_origin(sdk_base)
    scripts = " ".join(dict.fromkeys(x for x in (api, sdk) if x)) or "'none'"
    ancestors = " ".join(frame_ancestors) if frame_ancestors else "'none'"
    return ("default-src 'none'; "
            f"script-src {scripts}; connect-src {api} {ws}; "
            "style-src 'unsafe-inline'; img-src https: data: blob:; font-src https: data:; "
            f"media-src blob: data: {api}; worker-src blob:; "
            f"form-action 'self'; base-uri 'none'; frame-ancestors {ancestors}")


def _p(text: str, cls: str = "") -> str:
    return f'<p{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{escape(text)}</p>' if text else ""


def _h(tag: str, text: str) -> str:
    return f"<{tag}>{escape(text)}</{tag}>" if text else ""


def _sources(s: dict[str, Any], spec: dict[str, Any], site_url: Optional[str]) -> str:
    cites = [spec["sources"][x] for x in s.get("sources") or [] if x in (spec.get("sources") or {})]
    if not cites:
        return ""
    seen, items = set(), []
    for c in cites:
        label = c.get("label") or "Site content"
        if label in seen:
            continue
        seen.add(label)
        route = c.get("route")
        if site_url and route:
            items.append(f'<a href="{escape(site_url.rstrip("/") + route)}" rel="noopener">{escape(label)}</a>')
        else:
            items.append(escape(label))
    return f'<div class="src">Sources: {" · ".join(items)}</div>'


def render(spec: dict[str, Any], *, company: str, design: DesignSystem, public_key: str, api_base: str,
           sdk_base: str, base_path: str, query: dict[str, str], site_url: Optional[str],
           cta_url: str, embed: bool = False, sent: bool = False, preview: bool = False) -> str:
    c = design.colors
    bg = _color(c.get("background"), "#0c0b09")
    surface = _color(c.get("surface"), "#14161c")
    text_ = _color(c.get("text"), "#f3f5f7")
    muted = _color(c.get("muted"), "#9aa3b2")
    primary = _color(c.get("primary"), "#c9a24a")
    font = design.typography.get("font_family") or ""
    font = font if _FONT.match(font) else "ui-sans-serif, system-ui, sans-serif"
    radius = design.radius if _SIZE.match(design.radius or "") else "14px"
    logo = design.logo_url if (design.logo_url or "").startswith("https://") else ""

    keep = {k: v for k, v in query.items() if k in ("persona", "q", "account", "lang") or k.startswith("utm_")}
    qs = ("?" + urlencode(keep)) if keep else ""
    go = escape(f"{base_path}/go{qs}") if cta_url else "#enquiry"
    account = query.get("account_clean") or ""
    slots: list[dict[str, Any]] = []
    blocks: list[str] = []
    has_form = any(s["type"] == "enquiry_form" for s in spec["sections"])

    def button(label: str) -> str:
        if not label:
            return ""
        href = go if cta_url else ("#enquiry" if has_form else "")
        return f'<a class="btn" href="{href}">{escape(label)}</a>' if href else ""

    for s in spec["sections"]:
        t, p = s["type"], s.get("props") or {}
        inner = ""
        if t == "hero":
            eyebrow = (f"Prepared for {account}" if account else
                       (f"For {spec['persona_label']}" if spec.get("persona_label") else ""))
            inner = (f'<div class="eyebrow">{escape(eyebrow)}</div>' if eyebrow else "") + \
                f'<h1>{escape(p.get("title") or "")}</h1>' + _p(p.get("subtitle") or "", "lead") + \
                f'<div class="actions">{button(p.get("cta_label") or "")}</div>'
        elif t == "feature_grid":
            cards = "".join(f'<div class="card">{_h("h3", i.get("title") or "")}{_p(i.get("body") or "")}</div>'
                            for i in p.get("items") or [])
            inner = _h("h2", p.get("title") or "") + f'<div class="grid">{cards}</div>'
        elif t == "text":
            inner = _h("h2", p.get("title") or "") + _p(p.get("body") or "", "body")
        elif t == "pricing_table":
            tiers = "".join(
                f'<div class="card tier">{_h("h3", tr.get("name") or "")}'
                f'<div class="price">{escape(tr.get("price") or "")}</div>'
                f'<ul>{"".join(f"<li>{escape(f)}</li>" for f in tr.get("features") or [])}</ul></div>'
                for tr in p.get("tiers") or [])
            inner = _h("h2", p.get("title") or "") + f'<div class="grid">{tiers}</div>'
        elif t == "testimonials":
            quotes = "".join(
                f'<figure class="card quote"><blockquote>{escape(i["quote"])}</blockquote>'
                f'<figcaption>{escape(i["name"])}{(", " + escape(i["role"])) if i.get("role") else ""}'
                f'</figcaption></figure>' for i in p.get("items") or [])
            inner = _h("h2", p.get("title") or "") + f'<div class="grid">{quotes}</div>'
        elif t == "logos":
            imgs = "".join(f'<img src="{escape(i["src"])}" alt="{escape(i.get("alt") or "")}" loading="lazy" '
                           f'height="36">' for i in p.get("items") or [] if str(i.get("src", "")).startswith("https://"))
            inner = _h("h2", p.get("title") or "") + f'<div class="logos">{imgs}</div>'
        elif t == "faq":
            qa = "".join(f'<details class="qa"{" open" if n == 0 else ""}><summary>{escape(i["q"])}</summary>'
                         f'{_p(i["a"])}</details>' for n, i in enumerate(p.get("items") or []))
            inner = _h("h2", p.get("title") or "") + qa
        elif t == "comparison":
            head = "".join(f"<th>{escape(x)}</th>" for x in p.get("columns") or [])
            rows = "".join(f'<tr><th scope="row">{escape(r["label"])}</th>'
                           + "".join(f"<td>{escape(v)}</td>" for v in r.get("values") or []) + "</tr>"
                           for r in p.get("rows") or [])
            inner = _h("h2", p.get("title") or "") + \
                f'<div class="table"><table><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
        elif t in _SLOTTED:
            slot = f"s{len(slots)}"
            state = {k: v for k, v in p.items() if k != "title"}
            slots.append({"slot": slot, "component": {"component_type": _SLOTTED[t], "initial_state": state,
                                                      "explanation_text": p.get("title") or ""}})
            fallback = ("Turn on JavaScript to use the calculator." if t == "roi_calculator" else
                        " · ".join(f"{d['label']}: {d['value']}{p.get('unit') or ''}" for d in p.get("data") or []))
            inner = _h("h2", p.get("title") or "") + \
                f'<div class="comp" data-fb-slot="{slot}"><div class="fallback">{escape(fallback)}</div></div>'
        elif t == "enquiry_form":
            done = '<div class="sent" role="status">Thanks — the team will be in touch.</div>' if sent else ""
            hidden = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">' for k, v in keep.items())
            inner = (_h("h2", p.get("title") or "") + done +
                     f'<form class="form" method="post" action="{escape(base_path)}/lead">{hidden}'
                     '<label>Name<input name="name" autocomplete="name" maxlength="120"></label>'
                     '<label>Work email<input name="email" type="email" required autocomplete="email" maxlength="320"></label>'
                     '<label>Company<input name="company" autocomplete="organization" maxlength="120"'
                     f' value="{escape(account)}"></label>'
                     '<label class="wide">What would you like to know?<textarea name="message" rows="3" maxlength="2000">'
                     '</textarea></label>'
                     '<label class="hp" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off">'
                     f'</label><button class="btn" type="submit">{escape(p.get("submit_label") or "Send")}</button></form>')
            t = "enquiry"
        elif t == "cta":
            inner = _h("h2", p.get("title") or "") + _p(p.get("body") or "") + \
                f'<div class="actions">{button(p.get("cta_label") or "")}</div>'
        elif t == "media":
            inner = (f'<img class="media" src="{escape(p["src"])}" alt="{escape(p.get("alt") or "")}" loading="lazy">'
                     + _p(p.get("caption") or "", "caption"))
        if inner:
            sid = ' id="enquiry"' if t == "enquiry" else ""
            blocks.append(f'<section class="s s-{escape(t)}"{sid}>{inner}{_sources(s, spec, site_url)}</section>')

    data = json.dumps(slots, separators=(",", ":"), default=str).replace("<", "\\u003c")
    sdk = escape(f"{sdk_base.rstrip('/')}/fluid-buddha-page.global.js")
    loader = escape(f"{api_base.rstrip('/')}/widget/loader.js")
    head_logo = (f'<img src="{escape(logo)}" alt="{escape(company)}" class="logo">' if logo
                 else f'<span class="brand">{escape(company)}</span>')
    lang = "hi" if spec.get("lang") == "hi" else "en"
    banner = '<div class="preview">Preview — not counted, not public until the campaign is live.</div>' if preview else ""
    header = "" if embed else f"<header>{head_logo}</header>"
    footer = "" if embed else f"<footer>{escape(company)} · Powered by FluidBuddha</footer>"
    widget = "" if (embed or preview) else f'<script src="{loader}" data-key="{escape(public_key)}" async></script>'
    events = "" if preview else f' data-events="{escape(base_path)}/event"'
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><meta name="referrer" content="strict-origin-when-cross-origin">
<title>{escape(spec.get("title") or company)} · {escape(company)}</title>
<style>
:root{{--bg:{bg};--surface:{surface};--text:{text_};--muted:{muted};--primary:{primary};--radius:{radius};--fb-accent:{primary}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:{font};line-height:1.55}}
.wrap{{max-width:1040px;margin:0 auto;padding:24px 20px 64px}}
header{{display:flex;align-items:center;margin-bottom:20px}}.brand{{font-weight:700;color:var(--primary)}}.logo{{max-height:32px}}
.s{{margin:0 0 44px}}h1{{font-size:clamp(1.9rem,4.5vw,3rem);line-height:1.15;margin:8px 0 14px}}
h2{{font-size:1.45rem;margin:0 0 16px}}h3{{font-size:1.05rem;margin:0 0 6px}}
.s-hero{{padding:40px 0 12px}}.eyebrow{{color:var(--primary);font-weight:600;font-size:.9rem;letter-spacing:.02em}}
.lead{{font-size:1.15rem;color:var(--muted);max-width:720px}}.actions{{margin-top:22px}}
.btn{{display:inline-block;background:var(--primary);color:#111;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:10px;border:0;font:inherit;cursor:pointer}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:var(--surface);border-radius:var(--radius);padding:18px 20px;margin:0}}.card p{{margin:0;color:var(--muted)}}
.price{{font-size:1.5rem;font-weight:700;margin:4px 0 8px}}.tier ul{{padding-left:18px;margin:0;color:var(--muted)}}
blockquote{{margin:0 0 10px;font-size:1.02rem}}figcaption{{color:var(--muted);font-size:.88rem}}
.logos{{display:flex;flex-wrap:wrap;gap:28px;align-items:center;opacity:.85}}
.qa{{background:var(--surface);border-radius:var(--radius);padding:14px 18px;margin:0 0 10px}}.qa summary{{cursor:pointer;font-weight:600}}.qa p{{margin:10px 0 0;color:var(--muted)}}
.table{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid rgba(127,127,127,.25)}}
.body{{max-width:760px}}.comp{{min-height:120px}}.fallback{{color:var(--muted);font-style:italic}}
.form{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;background:var(--surface);border-radius:var(--radius);padding:20px;max-width:760px}}
.form label{{display:flex;flex-direction:column;gap:6px;font-size:.88rem;color:var(--muted)}}.form .wide{{grid-column:1/-1}}
.form input,.form textarea{{font:inherit;padding:10px 12px;border-radius:8px;border:1px solid rgba(127,127,127,.35);background:var(--bg);color:var(--text)}}
.form .hp{{position:absolute;left:-9999px}}.sent{{background:var(--surface);border-left:3px solid var(--primary);padding:12px 16px;margin:0 0 14px;border-radius:8px}}
.src{{color:var(--muted);font-size:.78rem;margin-top:10px}}.src a{{color:var(--muted)}}
.media{{max-width:100%;border-radius:var(--radius)}}.caption{{color:var(--muted);font-size:.85rem}}
.preview{{background:#7a5b00;color:#fff;text-align:center;padding:8px;font-size:.85rem}}
footer{{color:var(--muted);font-size:.78rem;margin-top:48px}}
</style></head>
<body>{banner}<div class="wrap">
{header}
{''.join(blocks)}
{footer}
</div>
<script type="application/json" id="fb-page-data">{data}</script>
<script src="{sdk}" defer{events}></script>
{widget}
</body></html>"""


def message(title: str, body: str, status_code: int = 404) -> str:
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title></head>'
            '<body style="font-family:system-ui,sans-serif;padding:60px 20px;text-align:center">'
            f'<h1 style="font-size:1.3rem">{escape(title)}</h1><p>{escape(body)}</p></body></html>')

