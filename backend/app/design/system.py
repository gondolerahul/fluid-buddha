"""
Design-system loader (Extreme intelligence, design-time ingestion).

The website owner supplies a per-site ``design-system.json`` (brand colours,
typography, radius, logo, brand voice). It is:
  * served to the SDK via ``GET /design-system`` so runtime-generated pages are
    themed with the owner's tokens, and
  * summarised into the Heavy Thinker prompt so generated COPY respects the brand
    voice (visual styling is never invented by the model — the frontend applies
    the tokens).

Resolution (P0-7): the design system an owner manages in the console
(``site_design_systems``) comes first. Then, mirroring the multi-site content
pipeline: a per-site env override
(``<SITE>_DESIGN_SYSTEM``) or a ``DESIGN_SYSTEM_DIR/<site>.json`` file. Without
a file, the tokens read off the site's own CSS at onboarding are used
(``site_design``, WS9; loaded by ``ensure_design``), else a sensible default
so the stack always runs.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT: dict[str, Any] = {
    "name": "Your Brand",
    "logo_url": "",
    "colors": {
        "primary": "#c9a24a",
        "secondary": "#232733",
        "background": "#0c0b09",
        "surface": "#14161c",
        "text": "#f3f5f7",
        "muted": "#9aa3b2",
        "accent": "#c9a24a",
    },
    "typography": {
        "font_family": "ui-sans-serif, system-ui, -apple-system, sans-serif",
        "heading_family": "",
        "base_size": "16px",
        "scale": 1.25,
    },
    "radius": "14px",
    "brand_voice": "Warm, clear, and confident. Speak plainly; avoid jargon.",
}


@dataclass
class DesignSystem:
    name: str
    logo_url: str
    colors: dict[str, str]
    typography: dict[str, Any]
    radius: str
    brand_voice: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DesignSystem":
        d = {**_DEFAULT, **(data or {})}
        d["colors"] = {**_DEFAULT["colors"], **(d.get("colors") or {})}
        d["typography"] = {**_DEFAULT["typography"], **(d.get("typography") or {})}
        return cls(
            name=str(d["name"]),
            logo_url=str(d.get("logo_url") or ""),
            colors=d["colors"],
            typography=d["typography"],
            radius=str(d.get("radius") or _DEFAULT["radius"]),
            brand_voice=str(d.get("brand_voice") or _DEFAULT["brand_voice"]),
            raw=d,
        )

    def to_tokens(self) -> dict[str, str]:
        """Flat CSS custom properties the SDK applies to the render surface."""
        tokens: dict[str, str] = {}
        for k, v in self.colors.items():
            tokens[f"--ds-color-{k}"] = str(v)
        tokens["--ds-font"] = str(self.typography.get("font_family", ""))
        tokens["--ds-font-heading"] = str(
            self.typography.get("heading_family") or self.typography.get("font_family", "")
        )
        tokens["--ds-base-size"] = str(self.typography.get("base_size", "16px"))
        tokens["--ds-radius"] = self.radius
        return tokens

    @property
    def tunables(self) -> dict[str, Any]:
        """Which tokens personalisation may vary, and within what range
        (strategy §4.2.1). Stored now; applied in Phase 3."""
        t = self.raw.get("tunables")
        return t if isinstance(t, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        d = {
            "name": self.name,
            "logo_url": self.logo_url,
            "colors": self.colors,
            "typography": self.typography,
            "radius": self.radius,
            "brand_voice": self.brand_voice,
            "tokens": self.to_tokens(),
        }
        if self.tunables:
            d["tunables"] = self.tunables
        if isinstance(self.raw.get("schemes"), dict) and self.raw["schemes"]:
            d["schemes"] = self.raw["schemes"]  # palettes for the scheme tunable (Phase 3)
        return d

    def to_prompt(self) -> str:
        palette = ", ".join(f"{k}={v}" for k, v in self.colors.items())
        return (
            f"DESIGN SYSTEM — brand '{self.name}'. Brand voice: {self.brand_voice} "
            f"Brand palette (applied automatically by the frontend; do not invent "
            f"colours): {palette}. Keep all generated copy on-brand in this voice."
        )


def _env_key(site_key: str) -> str:
    return site_key.upper().replace("-", "_")


def _design_path(site_key: str) -> Path | None:
    override = os.getenv(f"{_env_key(site_key)}_DESIGN_SYSTEM")
    if override:
        return Path(override)
    base = os.getenv("DESIGN_SYSTEM_DIR")
    if base:
        p = Path(base) / f"{site_key}.json"
        if p.exists():
            return p
    return None


_TTL_S = 30.0
# Designs extracted at onboarding, by site: (expires_at, data or None).
_extracted: dict[str, tuple[float, dict[str, Any] | None]] = {}
# Designs managed in the console (P0-7), by site: (expires_at, data or None).
_customer: dict[str, tuple[float, dict[str, Any] | None]] = {}


def remember_extracted(site_key: str, data: dict[str, Any] | None) -> None:
    _extracted[site_key] = (time.monotonic() + _TTL_S, data)


def remember_customer(site_key: str, data: dict[str, Any] | None) -> None:
    _customer[site_key] = (time.monotonic() + _TTL_S, data)


def forget(site_key: str) -> None:
    """Drop the cached console design for a site (after an edit)."""
    _customer.pop(site_key, None)


async def ensure_design(site_key: str) -> None:
    """Load the site's console and extracted designs into the cache unless fresh."""
    hit = _extracted.get(site_key)
    chit = _customer.get(site_key)
    now = time.monotonic()
    if hit and hit[0] > now and chit and chit[0] > now:
        return
    from app.db import session_scope
    from app.experience.store import get_design_system
    from app.onboarding.design import load_design

    try:
        async with session_scope() as db:
            data = await load_design(db, site_key)
            row = await get_design_system(db, site_key)
        custom = row["data"] if row else None
    except Exception as exc:  # never let a design read break a conversation
        logger.warning("design load failed for %s: %s", site_key, exc)
        data = hit[1] if hit else None
        custom = chit[1] if chit else None
    remember_extracted(site_key, data)
    remember_customer(site_key, custom)


def design_source(site_key: str) -> str:
    """Where the effective design comes from: console | file | extracted | default."""
    chit = _customer.get(site_key)
    if chit and chit[1]:
        return "console"
    if _load_file_design(site_key) is not None:
        return "file"
    hit = _extracted.get(site_key)
    return "extracted" if hit and hit[1] else "default"


def load_design_system(site_key: str) -> DesignSystem:
    """Console design → design-system file → extracted at onboarding → default."""
    chit = _customer.get(site_key)
    if chit and chit[1]:
        return DesignSystem.from_dict(chit[1])
    file_design = _load_file_design(site_key)
    if file_design is not None:
        return file_design
    hit = _extracted.get(site_key)
    return DesignSystem.from_dict(hit[1] if hit else None)


@lru_cache(maxsize=16)
def _load_file_design(site_key: str) -> DesignSystem | None:
    path = _design_path(site_key)
    if not (path and path.exists()):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("loaded design system for %s from %s", site_key, path)
    except Exception as exc:  # malformed file shouldn't break the stack
        logger.warning("failed to read design system %s: %s", path, exc)
        data = {}
    return DesignSystem.from_dict(data)
