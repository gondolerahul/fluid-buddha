"""
Persona / ICP definitions.

Each site's personas live in its agent profile (app/orchestrator/profile.py).
``PERSONAS`` below is HireBuddha's set, used to build its built-in profile; the
slugs match the HireBuddha frontend ``ICPSlug`` union so ``set_persona`` maps 1:1
onto that site's ``setICP`` mechanism.
"""
from __future__ import annotations

from typing import Optional

PERSONAS: dict[str, dict[str, str]] = {
    "startups": {
        "label": "Startups & SMEs",
        "focus": "speed to launch, lean teams, doing more with less",
        "tone": "energetic, practical, founder-to-founder",
        "landing": "/for/startups",
    },
    "solopreneurs": {
        "label": "Solopreneurs",
        "focus": "being a one-person company with an AI team behind you",
        "tone": "warm, empowering, concrete",
        "landing": "/for/solopreneurs",
    },
    "medium-enterprise": {
        "label": "Growing Companies",
        "focus": "operational control, scaling processes, removing silos",
        "tone": "confident, ops-savvy, ROI-aware",
        "landing": "/for/growing-companies",
    },
    "enterprise": {
        "label": "Enterprise",
        "focus": "security, compliance, integrations, deployment at scale",
        "tone": "precise, technical, trust-building",
        "landing": "/for/enterprise",
    },
}


def valid_personas(site_key: Optional[str]) -> list[str]:
    """Persona slugs the agent may switch to on this site."""
    from app.orchestrator.profile import profile_for  # avoid an import cycle

    return profile_for(site_key).persona_slugs


def persona_fragment(persona: str | None, site_key: Optional[str] = "hirebuddha") -> str:
    from app.orchestrator.profile import profile_for  # avoid an import cycle

    p = profile_for(site_key).persona(persona) if persona else None
    if p is None:
        return "The visitor's persona is not yet known — stay neutral and helpful."
    parts = [f"The visitor is in the '{p.label}' segment."]
    if p.focus:
        parts.append(f"Optimise for: {p.focus}.")
    if p.tone:
        parts.append(f"Tone: {p.tone}.")
    return " ".join(parts)
