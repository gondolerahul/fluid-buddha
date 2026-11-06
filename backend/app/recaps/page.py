"""
The recap page (M2-6): server-rendered HTML, branded with the site's design
tokens, readable without JavaScript. The components shown in the conversation
are drawn by the SDK's recap bundle (``fluid-buddha-recap.global.js``), which
reads their specs from a JSON block — there is no inline script, so the page's
CSP allows scripts from the SDK's origin only.

Every value is escaped; links are https only; the JSON block escapes ``<`` so
it can't close its own tag.
"""
from __future__ import annotations

import json
import re
from html import escape
from typing import Any, Optional
from urllib.parse import urlparse, urlsplit

from app.design.system import DesignSystem

_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$|^rgba?\([\d\s.,%]+\)$")
_FONT = re.compile(r"^[\w\s,\"'-]{1,200}$")
_SIZE = re.compile(r"^\d{1,3}(\.\d+)?(px|rem|em)$")


def _color(v: Any, fallback: str) -> str:
    return v if isinstance(v, str) and _COLOR.match(v.strip()) else fallback


def _paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return "".join(f"<p>{escape(p).replace(chr(10), '<br>')}</p>" for p in parts)


def sdk_origin(sdk_base: str) -> str:
    u = urlparse(sdk_base)
    return f"{u.scheme}://{u.netloc}" if u.scheme in ("http", "https") and u.netloc else ""


def embed_origins(recap: dict) -> list[str]:
    """https origins of the site's own embedded components shown in this recap
    (M2-8 follow-up): the only frames the page may load."""
    out: list[str] = []
    for turn in (recap.get("content") or {}).get("turns") or []:
        for c in turn.get("components") or []:
            if c.get("component_type") != "embed":
                continue
            src = str((c.get("initial_state") or {}).get("src") or "")
            parts = urlsplit(src)
            if parts.scheme == "https" and parts.netloc and re.fullmatch(r"[A-Za-z0-9.:-]+", parts.netloc):
                origin = f"https://{parts.netloc}"
                if origin not in out:
                    out.append(origin)
    return out[:8]


def csp(sdk_base: str, frames: Optional[list[str]] = None) -> str:
    origin = sdk_origin(sdk_base)
    frame_src = f"frame-src {' '.join(frames)}; " if frames else ""
    return ("default-src 'none'; "
            f"script-src {origin or chr(39) + 'none' + chr(39)}; "
            "style-src 'unsafe-inline'; img-src https: data:; font-src https: data:; "
            + frame_src +
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def render(recap: dict, *, company: str, agent_name: str, design: DesignSystem,
           site_url: Optional[str], cta_label: str, cta_url: str, sdk_base: str) -> str:
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

    content = recap["content"]
    turns = content.get("turns") or []
    slots: list[dict[str, Any]] = []
    blocks = []
    for i, t in enumerate(turns):
        comp_html = ""
        for comp in t.get("components") or []:
            slot = f"c{len(slots)}"
            slots.append({"slot": slot, "component": comp})
            caption = escape(str(comp.get("explanation_text") or comp.get("component_type") or ""))
            comp_html += (f'<div class="comp" data-fb-slot="{slot}">'
                          f'<div class="comp-fallback">{caption}</div></div>')
        srcs = "".join(
            f'<li><a href="{escape(s["url"])}" rel="noopener noreferrer">{escape(s["label"])}</a></li>'
            if s.get("url") else f'<li>{escape(s["label"])}</li>'
            for s in t.get("sources") or [])
        blocks.append(
            f'<section class="turn"><div class="q">{escape(t["question"])}</div>'
            f'<div class="a">{_paragraphs(t.get("answer") or "")}</div>{comp_html}'
            + (f'<ul class="src"><li class="src-h">Sources</li>{srcs}</ul>' if srcs else "")
            + "</section>")

    steps = []
    if cta_url.startswith("https://") and cta_label:
        steps.append(f'<a class="btn" href="{escape(cta_url)}" rel="noopener">{escape(cta_label)}</a>')
    if site_url:
        steps.append(f'<a class="btn ghost" href="{escape(site_url)}" rel="noopener">'
                     f'Ask {escape(agent_name)} a follow-up</a>')

    data = json.dumps(slots, separators=(",", ":"), default=str).replace("<", "\\u003c")
    expires = str(recap["expires_at"].date()) if hasattr(recap["expires_at"], "date") else ""
    sdk = f"{sdk_base.rstrip('/')}/fluid-buddha-recap.global.js"
    head_logo = (f'<img src="{escape(logo)}" alt="{escape(company)}" class="logo">' if logo
                 else f'<span class="brand">{escape(company)}</span>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">
<title>Your conversation with {escape(company)}</title>
<style>
:root{{--bg:{bg};--surface:{surface};--text:{text_};--muted:{muted};--primary:{primary};--radius:{radius};--fb-accent:{primary}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:{font};line-height:1.55}}
.wrap{{max-width:760px;margin:0 auto;padding:32px 20px 60px}}
header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}}
.brand{{font-weight:700;color:var(--primary)}}.logo{{max-height:32px}}
h1{{font-size:1.6rem;margin:0 0 8px}}.meta{{color:var(--muted);font-size:.85rem;margin-bottom:22px}}
.summary{{background:var(--surface);border-radius:var(--radius);padding:18px 20px;margin-bottom:26px}}.summary p:last-child{{margin:0}}
.turn{{margin:0 0 26px}}.q{{font-weight:600;margin-bottom:8px;padding-left:12px;border-left:3px solid var(--primary)}}
.a p{{margin:0 0 10px}}.comp{{margin:12px 0}}.comp-fallback{{color:var(--muted);font-size:.85rem;font-style:italic}}
.src{{list-style:none;padding:0;margin:8px 0 0;font-size:.82rem;color:var(--muted)}}.src li{{display:inline;margin-right:12px}}
.src-h{{font-weight:600}}.src a{{color:var(--muted)}}
.steps{{display:flex;gap:10px;flex-wrap:wrap;margin:30px 0}}
.btn{{background:var(--primary);color:#111;text-decoration:none;font-weight:600;padding:11px 18px;border-radius:10px}}
.btn.ghost{{background:transparent;color:var(--text);border:1px solid var(--muted)}}
footer{{color:var(--muted);font-size:.78rem;margin-top:40px}}
</style></head>
<body><div class="wrap">
<header>{head_logo}</header>
<h1>Your conversation with {escape(agent_name)}</h1>
<div class="meta">{escape(company)} · link works until {escape(expires)}</div>
<div class="summary">{_paragraphs(content.get("summary") or "")}</div>
{''.join(blocks)}
<div class="steps">{''.join(steps)}</div>
<footer>A recap of a conversation on {escape(company)}'s website. Personal details stay hidden.
Powered by FluidBuddha.</footer>
</div>
<script type="application/json" id="fb-recap-data">{data}</script>
<script src="{escape(sdk)}" defer></script>
</body></html>"""


def not_found() -> str:
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex">'
            '<title>Recap not available</title></head><body style="font-family:system-ui,sans-serif;'
            'padding:60px 20px;text-align:center"><h1 style="font-size:1.3rem">This recap isn\'t available</h1>'
            '<p>The link may have expired or been removed.</p></body></html>')
