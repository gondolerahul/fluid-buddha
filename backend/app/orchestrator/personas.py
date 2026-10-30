"""
Persona / ICP definitions.

Slugs match the frontend ``ICPSlug`` union exactly so ``set_persona`` maps 1:1
onto the site's existing ``setICP`` mechanism.
"""
from __future__ import annotations

# Must equal the frontend ICPContext ICPSlug values.
VALID_PERSONAS = {"medium-enterprise", "startups", "solopreneurs", "enterprise"}

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


def persona_fragment(persona: str | None) -> str:
    if not persona or persona not in PERSONAS:
        return "The visitor's persona is not yet known — stay neutral and helpful."
    p = PERSONAS[persona]
    return (
        f"The visitor is in the '{p['label']}' segment. "
        f"Optimise for: {p['focus']}. Tone: {p['tone']}."
    )
