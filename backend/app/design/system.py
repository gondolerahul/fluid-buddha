"""
Design-system loader (Extreme intelligence, design-time ingestion).

The website owner supplies a per-site ``design-system.json`` (brand colours,
typography, radius, logo, brand voice). It is:
  * served to the SDK via ``GET /design-system`` so runtime-generated pages are
    themed with the owner's tokens, and
  * summarised into the Heavy Thinker prompt so generated COPY respects the brand
    voice (visual styling is never invented by the model — the frontend applies
    the tokens).

Resolution mirrors the multi-site content pipeline: a per-site env override
(``<SITE>_DESIGN_SYSTEM``) or a ``DESIGN_SYSTEM_DIR/<site>.json`` file. With no
file present a sensible default is returned so the stack always runs.
"""
from __future__ import annotations

import json
import logging
import os
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "logo_url": self.logo_url,
            "colors": self.colors,
            "typography": self.typography,
            "radius": self.radius,
            "brand_voice": self.brand_voice,
            "tokens": self.to_tokens(),
        }

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


@lru_cache(maxsize=16)
def load_design_system(site_key: str) -> DesignSystem:
    path = _design_path(site_key)
    data: dict[str, Any] = {}
    if path and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info("loaded design system for %s from %s", site_key, path)
        except Exception as exc:  # malformed file shouldn't break the stack
            logger.warning("failed to read design system %s: %s", path, exc)
    return DesignSystem.from_dict(data)
