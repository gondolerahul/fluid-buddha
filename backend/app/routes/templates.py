"""
Vertical templates (M2-9).

    GET  /tenant/templates                                the packs
    GET  /tenant/websites/{id}/template/preview?template=  what applying would change
    POST /tenant/websites/{id}/template   {template}       apply (keeps hand edits)

A template can also be picked when creating a website (``template`` on
``POST /tenant/websites``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import templates
from app.db import get_session
from app.orchestrator.profile import load_profile
from app.tenancy import store
from app.tenancy.deps import current_tenant, owned_website
from app.templates import apply as tapply

router = APIRouter(prefix="/tenant", tags=["templates"])


class ApplyIn(BaseModel):
    template: str


def _pack(template_id: str) -> templates.TemplatePack:
    pack = templates.get(template_id)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such template")
    return pack


@router.get("/templates")
async def list_templates(_: store.Tenant = Depends(current_tenant)) -> dict:
    return {"templates": [p.summary() for p in templates.packs().values()]}


@router.get("/websites/{website_id}/template/preview")
async def preview(template: str, site: store.Website = Depends(owned_website),
                  db: AsyncSession = Depends(get_session)) -> dict:
    return (await tapply.preview(db, site.site_key, _pack(template))).to_dict()


@router.get("/websites/{website_id}/template")
async def current(site: store.Website = Depends(owned_website),
                  db: AsyncSession = Depends(get_session)) -> dict:
    t = (await load_profile(db, site.site_key)).template or {}
    pack = templates.get(t.get("id"))
    return {"template": t.get("id"), "name": pack.name if pack else None,
            "applied_at": t.get("applied_at")}


@router.post("/websites/{website_id}/template")
async def apply_template(body: ApplyIn, site: store.Website = Depends(owned_website),
                         db: AsyncSession = Depends(get_session)) -> dict:
    plan = await tapply.apply(db, site.site_key, _pack(body.template))
    await db.commit()
    return plan.to_dict()
