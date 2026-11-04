"""
Read a site's brand off its homepage (WS9): colours, fonts, corner radius,
logo and name, from the page's own CSS and metadata.

Signals, strongest first:
  * CSS custom properties with brand-ish names (``--primary``, ``--brand-color``,
    ``--color-accent``…);
  * the ``body`` rule's background, colour and font, and the heading font;
  * ``<meta name="theme-color">``;
  * otherwise the most used saturated colour, and the most used radius.

The result is a partial design system (only what was found); defaults fill the
rest when it is loaded. Stored per site in ``site_design``; an owner's
``design-system.json`` still takes precedence (``app.design.system``).
"""
from __future__ import annotations

import colorsys
import json
import re
from collections import Counter
from typing import Any, Optional
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.onboarding.html import PageInfo

_HEX = r"#(?:[0-9a-fA-F]{3}){1,2}\b"
_RGB = r"rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(?:\s*,\s*[\d.]+)?\s*\)"
_COLOR_RE = re.compile(f"{_HEX}|{_RGB}")
_VAR_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+)")
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+)")

_ROLE_HINTS = {
    "primary": ("primary", "brand", "main"),
    "accent": ("accent", "highlight", "cta"),
    "secondary": ("secondary",),
    "background": ("background", "bg"),
    "text": ("text", "foreground", "fg", "body-color"),
}


def hex_color(value: str) -> Optional[str]:
    """``#abc`` / ``#aabbcc`` / ``rgb()`` → ``#aabbcc``; None if not a colour."""
    v = (value or "").strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)
    m = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([\d.]+))?\s*\)", v)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.5:
            return None  # mostly transparent: not a brand colour
        r, g, b = (min(255, int(x)) for x in m.group(1, 2, 3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


def _saturation(hex_: str) -> tuple[float, float]:
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    return s, lum


def _is_brandish(hex_: str) -> bool:
    s, lum = _saturation(hex_)
    return s >= 0.35 and 0.18 <= lum <= 0.82


def _first_font(value: str) -> str:
    v = re.sub(r"\s*!important\s*$", "", value.strip())
    return v if v and not v.startswith("var(") and v.lower() not in ("inherit", "initial") else ""


def extract_design(home: PageInfo, css_texts: list[str]) -> dict[str, Any]:
    css = "\n".join([home.inline_css, *css_texts])
    # Custom properties: resolve one level of var() for brand-named variables.
    variables = {name.lower(): val.strip() for name, val in _VAR_RE.findall(css)}

    def resolve(val: str) -> str:
        m = re.fullmatch(r"var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)", val.strip())
        if m:
            return variables.get(m.group(1).lower(), m.group(2) or "")
        return val

    colors: dict[str, str] = {}
    for name, raw in variables.items():
        c = hex_color(resolve(raw))
        if not c:
            continue
        key = name.lstrip("-")
        for role, hints in _ROLE_HINTS.items():
            if role in colors:
                continue
            if any(h in key for h in hints) and not any(
                x in key for x in ("hover", "light", "dark", "muted", "border", "shadow", "rgb")
            ):
                colors[role] = c
                break

    fonts: dict[str, str] = {}
    radii: Counter[str] = Counter()
    for selector, body in _RULE_RE.findall(css):
        sels = {s.strip().lower() for s in selector.split(",")}
        decls = {k.lower(): resolve(v) for k, v in _DECL_RE.findall(body)}
        if sels & {"body", "html", ":root"}:
            bg = hex_color(decls.get("background-color", "") or decls.get("background", ""))
            if bg and "background" not in colors:
                colors["background"] = bg
            fg = hex_color(decls.get("color", ""))
            if fg and "text" not in colors:
                colors["text"] = fg
            if decls.get("font-family") and "body" not in fonts:
                fonts["body"] = _first_font(decls["font-family"])
        if sels & {"h1", "h2", "h1, h2"} and decls.get("font-family") and "heading" not in fonts:
            fonts["heading"] = _first_font(decls["font-family"])
        r = decls.get("border-radius", "").strip()
        if re.fullmatch(r"\d+(\.\d+)?(px|rem)", r) and r not in ("0px", "0rem"):
            radii[r] += 1

    theme = hex_color(home.theme_color)
    if "primary" not in colors:
        if theme and _is_brandish(theme):
            colors["primary"] = theme
        else:
            counts = Counter(c for c in (hex_color(m) for m in _COLOR_RE.findall(css))
                             if c and _is_brandish(c))
            if counts:
                colors["primary"] = counts.most_common(1)[0][0]
    if "accent" not in colors and "primary" in colors:
        colors["accent"] = colors["primary"]

    design: dict[str, Any] = {}
    name = home.site_name or re.split(r"\s+[|\-–—:·]\s+", home.title or "")[0].strip()
    if name:
        design["name"] = name[:80]
    logo = (home.logo_candidates or home.icons or [home.og_image or ""])[0]
    if logo:
        design["logo_url"] = logo
    if colors:
        design["colors"] = colors
    typo: dict[str, str] = {}
    if fonts.get("body"):
        typo["font_family"] = fonts["body"]
    if fonts.get("heading"):
        typo["heading_family"] = fonts["heading"]
    if typo:
        design["typography"] = typo
    if radii:
        design["radius"] = radii.most_common(1)[0][0]
    return design


def same_site_stylesheets(home: PageInfo, limit: int = 4) -> list[str]:
    host = (urlsplit(home.url).hostname or "").lower().removeprefix("www.")
    out = []
    for href in home.stylesheets:
        h = (urlsplit(href).hostname or "").lower().removeprefix("www.")
        if h == host and href not in out:
            out.append(href)
        if len(out) >= limit:
            break
    return out


# ---- storage -----------------------------------------------------------------

async def save_design(db: AsyncSession, site_key: str, design: dict, source_url: str) -> None:
    await db.execute(
        text("INSERT INTO site_design (site_key, design, source_url, updated_at) "
             "VALUES (:k, CAST(:d AS jsonb), :u, now()) "
             "ON CONFLICT (site_key) DO UPDATE SET design = CAST(:d AS jsonb), "
             "source_url = :u, updated_at = now()"),
        {"k": site_key, "d": json.dumps(design), "u": source_url},
    )
    await db.commit()


async def load_design(db: AsyncSession, site_key: str) -> Optional[dict]:
    if not (await db.execute(text("SELECT to_regclass('site_design')"))).scalar():
        return None
    row = (await db.execute(
        text("SELECT design FROM site_design WHERE site_key = :k"), {"k": site_key}
    )).scalar()
    if row is None:
        return None
    return row if isinstance(row, dict) else json.loads(row)
