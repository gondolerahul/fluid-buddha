"""
Personalisation within brand limits (P3-3) and "why am I seeing this" (P3-5).

``apply_tunables`` turns a taste profile into design-token overrides, but only
on the axes the design system's ``tunables`` allow and only to values listed
there: personalisation can never produce a design the brand team hasn't
allowed (strategy §5.4).

``explain`` says, in plain words, which signals shaped what a visitor sees.
"""
from __future__ import annotations

import re
from typing import Optional

from app.design.system import DesignSystem
from app.experience.intent import Intent, Signals
from app.experience.taste import Taste

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

DENSITY = {"airy": {"--ds-gap": "52px", "--ds-pad": "28px"},
           "balanced": {"--ds-gap": "34px", "--ds-pad": "20px"},
           "compact": {"--ds-gap": "18px", "--ds-pad": "14px"}}
MOTION = {"calm": {"--ds-anim": "0s"}, "standard": {"--ds-anim": ".6s"}, "lively": {"--ds-anim": ".9s"}}
TYPE_SCALE = {"small": "15px", "standard": "16px", "large": "18px"}


def _allowed(design: DesignSystem, axis: str) -> tuple[list[str], Optional[str]]:
    t = design.tunables.get(axis) if isinstance(design.tunables, dict) else None
    if not isinstance(t, dict):
        return [], None
    allowed = [str(x) for x in (t.get("allowed") or [])]
    default = t.get("default") if t.get("default") in allowed else None
    return allowed, default


def apply_tunables(design: DesignSystem, taste: Optional[Taste]) -> tuple[dict[str, str], dict[str, str]]:
    """``(token overrides, {axis: value applied})``. Untouched axes keep the brand's tokens."""
    tokens: dict[str, str] = {}
    applied: dict[str, str] = {}

    def pick(axis: str, wanted: Optional[str]) -> Optional[str]:
        allowed, default = _allowed(design, axis)
        if not allowed:
            return None
        return wanted if wanted in allowed else default

    dens = pick("density", taste.value("density") if taste else None)
    if dens in DENSITY:
        tokens.update(DENSITY[dens])
        applied["density"] = dens
    motion = pick("motion", taste.value("motion") if taste else None)
    if motion in MOTION:
        tokens.update(MOTION[motion])
        applied["motion"] = motion
    scale = pick("type_scale", None)  # not a taste dimension yet: the brand's default only
    if scale in TYPE_SCALE:
        tokens["--ds-base-size"] = TYPE_SCALE[scale]
        applied["type_scale"] = scale
    scheme = pick("scheme", taste.value("scheme") if taste else None)
    schemes = design.raw.get("schemes") if isinstance(design.raw.get("schemes"), dict) else {}
    if scheme in ("light", "dark") and isinstance(schemes.get(scheme), dict):
        for k, v in schemes[scheme].items():
            if re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", str(k)) and _HEX.match(str(v)):
                tokens[f"--ds-color-{k}"] = str(v)
        applied["scheme"] = scheme
    return tokens, applied


def themed_tokens(design: DesignSystem, taste: Optional[Taste]) -> dict[str, str]:
    return {**design.to_tokens(), **apply_tunables(design, taste)[0]}


_STAGE_WORDS = {"learn": "getting to know us", "evaluate": "comparing options", "buy": "ready to talk",
                "customer": "already a customer"}


def explain(intent: Optional[Intent], sig: Signals, taste: Optional[Taste], *, served: str = "",
            applied: Optional[dict[str, str]] = None) -> list[str]:
    """Plain-language reasons, most important first (empty when nothing personal)."""
    out: list[str] = []
    if served in ("pinned", "canonical"):
        out.append("This is the version the site's team picked for this page")
    if intent and intent.family != "general":
        if intent.source == "rule" and sig.utm_campaign:
            out.append(f"You arrived from the \"{sig.utm_campaign}\" campaign, so this focuses on {intent.label.lower()}")
        elif intent.source == "rule":
            out.append(f"You're on {sig.page}, so this focuses on {intent.label.lower()}")
        elif sig.query or sig.referrer_terms:
            out.append(f"Your search ({(sig.query or sig.referrer_terms)[:60]}) looked like {intent.label.lower()}")
        else:
            out.append(f"It looks like you're {_STAGE_WORDS.get(intent.stage, intent.label.lower())}")
    if taste:
        brief = []
        if taste.value("detail") == "summary":
            brief.append("short summaries")
        elif taste.value("detail") == "deep":
            brief.append("more detail")
        fmt = taste.value("format")
        if fmt in ("tables", "charts", "visuals", "bullets"):
            brief.append(fmt)
        dens = (applied or {}).get("density")
        # Only when the layout follows the visitor's taste, not the brand's default.
        if dens in ("compact", "airy") and taste.value("density") == dens:
            brief.append("an airy layout" if dens == "airy" else "a compact layout")
        if brief:
            chosen = any(taste.dims.get(d, {}).get("source") == "explicit" for d in ("detail", "format", "density"))
            out.append(("You asked for " if chosen else "You seem to prefer ") + ", ".join(brief))
    return out[:3]
