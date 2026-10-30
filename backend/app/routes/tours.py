"""
Guided-tour view/edit (req D).

A tenant can read the stored tour plan for a website, regenerate it from the
site's ingested content, and save manual edits. The plan is persisted in the
``site_tours`` table (``app/orchestrator/tour_store.py``) and the runtime already
streams it to the SDK via ``EVENTS/tour_plan`` — so edits take effect on the next
visit with no extra wiring.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.orchestrator import tour_store
from app.orchestrator.tour import TourPlan
from app.tenancy import store
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["tour"])


class TourStopIn(BaseModel):
    narration: str = Field(..., min_length=1)
    move: dict | None = None
    label: str = ""


class TourPlanIn(BaseModel):
    stops: list[TourStopIn] = Field(default_factory=list)


def _plan_payload(plan: TourPlan | None, site_key: str) -> dict:
    if plan is None:
        return {"site_key": site_key, "stops": [], "exists": False}
    return {**plan.to_dict(), "exists": True}


@router.get("/tour")
async def get_tour(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    plan = await tour_store.load_plan(db, site.site_key)
    return _plan_payload(plan, site.site_key)


@router.put("/tour")
async def save_tour(
    body: TourPlanIn,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    plan = TourPlan.from_dict({
        "site_key": site.site_key,
        "stops": [s.model_dump() for s in body.stops],
    })
    if not [s for s in plan.stops if s.narration]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A tour needs at least one stop with narration.")
    await tour_store.save_plan(db, plan)
    return _plan_payload(plan, site.site_key)


@router.post("/tour/generate")
async def generate_tour(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Author a fresh tour from the site's ingested sources (or legacy file copy)
    and persist it. Lets a tenant bootstrap a tour they can then edit."""
    from app.ai.factory import build_engines
    from app.config import get_settings
    from app.orchestrator.tour import plan_tour
    from app.tenancy import sources as src_store
    from ingestion.scraper import SourceDocument, load_site_documents

    rows = await src_store.list_sources(db, site.id)
    documents = [
        SourceDocument(filename=r.name, route=None, content=r.content)
        for r in rows if r.status == "ingested" and (r.content or "").strip()
    ]
    if not documents:  # legacy sites whose content is on disk, not in tenant_sources
        documents = load_site_documents(site.site_key)
    if not documents:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "No ingested content yet — add sources and run ingestion first.")

    settings = get_settings()
    engines = build_engines(settings)
    plan = await plan_tour(site_key=site.site_key, documents=documents,
                           llm=engines.llm, settings=settings)
    await tour_store.save_plan(db, plan)
    return _plan_payload(plan, site.site_key)
