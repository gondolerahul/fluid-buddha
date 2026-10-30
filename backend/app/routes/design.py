"""Design-system endpoint (Extreme intelligence).

Serves a site's brand tokens so the SDK can theme runtime-generated pages with
the owner's colours/typography. CORS-gated like ``/chat``; the SDK fetches it
once when ``intelligence='extreme'``.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.design.system import load_design_system

router = APIRouter(tags=["design"])


@router.get("/design-system")
async def design_system(site: str = "hirebuddha") -> dict:
    return load_design_system(site).to_dict()
