"""
Console API for the generative experience configuration (P0-7, P0-9).

Design system (one current version per site; Editor):

    GET    /tenant/websites/{id}/design-system   → {current, effective, source}
    PUT    /tenant/websites/{id}/design-system   → save (validated)
    DELETE /tenant/websites/{id}/design-system   → back to file / extracted / default

Component manifest versions (drafts by Editors, approval by Admins):

    GET    /tenant/websites/{id}/manifest                         → active + versions
    GET    /tenant/websites/{id}/manifest/versions/{v}            → one version + check
    POST   /tenant/websites/{id}/manifest/versions                → new draft
    PUT    /tenant/websites/{id}/manifest/versions/{v}            → edit a draft
    DELETE /tenant/websites/{id}/manifest/versions/{v}            → delete a draft
    POST   /tenant/websites/{id}/manifest/versions/{v}/approve    → approve (Admin)
    POST   /tenant/websites/{id}/manifest/drafts/storybook        → draft from Storybook
    POST   /tenant/websites/{id}/manifest/drafts/site             → draft from the live site
"""
from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.design import system as design
from app.experience import drafts, manifest as mf, store as xstore
from app.tenancy import store
from app.tenancy.deps import owned_website
from app.tenancy.url_fetch import UnsafeURLError, check_url, fetch_public

router = APIRouter(prefix="/tenant/websites/{website_id}", tags=["experience"])

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
_CSS_VALUE_RE = re.compile(r"^[\w\s.,#%()'\"-]{0,200}$")
_TUNABLE_AXES = ("density", "scheme", "motion", "type_scale")


def _actor(request: Request) -> Optional[str]:
    m = getattr(request.state, "member", None)
    return getattr(m, "email", None)


# ---- design system ----------------------------------------------------------

class Tunable(BaseModel):
    allowed: list[str] = Field(default_factory=list, max_length=8)
    default: Optional[str] = Field(None, max_length=40)

    @field_validator("allowed")
    @classmethod
    def _short(cls, v: list[str]) -> list[str]:
        return [str(x)[:40] for x in v]


class DesignSystemIn(BaseModel):
    name: str = Field("", max_length=120)
    logo_url: str = Field("", max_length=1000)
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, Any] = Field(default_factory=dict)
    radius: str = Field("", max_length=20)
    brand_voice: str = Field("", max_length=600)
    tunables: dict[str, Tunable] = Field(default_factory=dict)
    # Optional palettes for the scheme tunable (Phase 3): {"dark": {"background": "#000", …}}.
    schemes: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("schemes")
    @classmethod
    def _schemes(cls, v: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        bad = [k for k in v if k not in ("light", "dark")]
        if bad:
            raise ValueError("schemes may only be light and dark")
        for name, colors in v.items():
            if len(colors) > 24:
                raise ValueError("at most 24 colours per scheme")
            for k, c in colors.items():
                if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", k) or not _HEX_RE.match(str(c)):
                    raise ValueError(f"{name} colour {k!r} must be a hex value such as #1a2b3c")
        return v

    @field_validator("logo_url")
    @classmethod
    def _https(cls, v: str) -> str:
        if v and not v.startswith("https://"):
            raise ValueError("logo_url must be an https:// URL")
        return v

    @field_validator("colors")
    @classmethod
    def _colors(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 24:
            raise ValueError("at most 24 colours")
        for k, c in v.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", k) or not _HEX_RE.match(str(c)):
                raise ValueError(f"colour {k!r} must be a hex value such as #1a2b3c")
        return v

    @field_validator("typography")
    @classmethod
    def _typography(cls, v: dict[str, Any]) -> dict[str, Any]:
        allowed = {"font_family", "heading_family", "base_size", "scale"}
        out: dict[str, Any] = {}
        for k, val in v.items():
            if k not in allowed:
                continue
            if k == "scale":
                try:
                    out[k] = max(1.0, min(2.0, float(val)))
                except (TypeError, ValueError):
                    raise ValueError("typography.scale must be a number")
            elif not _CSS_VALUE_RE.match(str(val)):
                raise ValueError(f"typography.{k} has characters a font value can't use")
            else:
                out[k] = str(val)
        return out

    @field_validator("radius")
    @classmethod
    def _radius(cls, v: str) -> str:
        if v and not re.fullmatch(r"\d{1,3}(px|rem|em|%)", v):
            raise ValueError("radius must look like 14px, 1rem or 50%")
        return v

    @field_validator("tunables")
    @classmethod
    def _tunables(cls, v: dict[str, Tunable]) -> dict[str, Tunable]:
        bad = [k for k in v if k not in _TUNABLE_AXES]
        if bad:
            raise ValueError(f"tunables may only cover {', '.join(_TUNABLE_AXES)}")
        return v


async def _design_view(site_key: str, db: AsyncSession) -> dict[str, Any]:
    design.forget(site_key)
    await design.ensure_design(site_key)
    row = await xstore.get_design_system(db, site_key)
    return {
        "current": row,
        "effective": design.load_design_system(site_key).to_dict(),
        "source": design.design_source(site_key),
    }


@router.get("/design-system")
async def get_design_system(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await _design_view(site.site_key, db)


@router.put("/design-system")
async def put_design_system(
    body: DesignSystemIn,
    request: Request,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    data = body.model_dump(exclude_defaults=False)
    data["tunables"] = {k: t.model_dump() for k, t in body.tunables.items()}
    data = {k: v for k, v in data.items() if v not in ("", {}, None)}
    await xstore.put_design_system(db, site.site_key, data, _actor(request))
    return await _design_view(site.site_key, db)


@router.delete("/design-system")
async def delete_design_system(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    await xstore.delete_design_system(db, site.site_key)
    return await _design_view(site.site_key, db)


# ---- manifest versions ------------------------------------------------------

class ManifestIn(BaseModel):
    data: dict[str, Any]
    notes: str = Field("", max_length=1000)


def _check(data: Any) -> dict[str, Any]:
    """What the planner would see for this manifest data, and what it refused."""
    parsed, problems = mf.parse_manifest(data, source="console")
    custom = [e.to_dict() for e in parsed.entries() if not e.id.startswith("fb.")]
    return {"problems": problems, "components": custom,
            "component_count": len(parsed.entries()), "bundle": parsed.bundle}


def _version_view(v: dict[str, Any]) -> dict[str, Any]:
    return {**v, "check": _check(v.get("data"))}


@router.get("/manifest")
async def get_manifest(
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    active = await xstore.approved_manifest(db, site.site_key)
    mf.remember_approved(site.site_key, active["data"] if active else None,
                         active["version"] if active else None)
    effective = mf.load_manifest(site.site_key)
    return {
        "source": effective.source,
        "active_version": active["version"] if active else None,
        "active": _version_view(active) if active else None,
        "effective": {
            "bundle": effective.bundle,
            "components": [e.to_dict() for e in effective.entries()],
        },
        "versions": await xstore.list_versions(db, site.site_key),
    }


async def _version_or_404(db: AsyncSession, site_key: str, version: int) -> dict[str, Any]:
    v = await xstore.get_version(db, site_key, version)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return v


@router.get("/manifest/versions/{version}")
async def get_manifest_version(
    version: int,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    return _version_view(await _version_or_404(db, site.site_key, version))


def _require_object(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The manifest must be a JSON object.")
    if len(str(data)) > 400_000:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The manifest is too large.")
    return data


@router.post("/manifest/versions", status_code=status.HTTP_201_CREATED)
async def create_manifest_version(
    body: ManifestIn,
    request: Request,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    created = await xstore.create_version(
        db, site.site_key, _require_object(body.data), source="manual",
        notes=body.notes, actor=_actor(request))
    return _version_view(created)


@router.put("/manifest/versions/{version}")
async def update_manifest_draft(
    version: int,
    body: ManifestIn,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cur = await _version_or_404(db, site.site_key, version)
    if cur["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Only drafts can be edited; approved versions never change.")
    await xstore.update_draft(db, site.site_key, version, _require_object(body.data), body.notes)
    return _version_view(await _version_or_404(db, site.site_key, version))


@router.delete("/manifest/versions/{version}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manifest_draft(
    version: int,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> None:
    cur = await _version_or_404(db, site.site_key, version)
    if cur["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be deleted.")
    await xstore.delete_draft(db, site.site_key, version)


@router.post("/manifest/versions/{version}/approve")
async def approve_manifest_version(
    version: int,
    request: Request,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cur = await _version_or_404(db, site.site_key, version)
    if cur["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a draft can be approved.")
    check = _check(cur["data"])
    if check["problems"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {
            "message": "Fix these before approving.", "problems": check["problems"]})
    approved = await xstore.approve_version(db, site.site_key, version, _actor(request))
    if approved is None:  # raced with another approval
        raise HTTPException(status.HTTP_409_CONFLICT, "This version changed; reload and try again.")
    mf.forget(site.site_key)
    mf.remember_approved(site.site_key, approved["data"], approved["version"])
    return _version_view(approved)


# ---- drafts (P0-9) ----------------------------------------------------------

class StorybookDraftIn(BaseModel):
    url: Optional[str] = Field(None, max_length=2000)
    index: Optional[dict[str, Any]] = None
    docgen: Optional[Any] = None


class SiteDraftIn(BaseModel):
    url: Optional[str] = Field(None, max_length=2000)
    max_pages: int = Field(5, ge=1, le=drafts.MAX_SITE_PAGES)


def _safe_url(raw: str) -> str:
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    try:
        check_url(raw)
    except UnsafeURLError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    return raw


async def _save_draft(
    db: AsyncSession, site_key: str, draft: dict[str, Any], source: str, actor: Optional[str],
) -> dict[str, Any]:
    if not draft["found"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "No components were found, so no draft was made.")
    created = await xstore.create_version(db, site_key, draft["data"], source=source,
                                          notes=draft["notes"], actor=actor)
    return _version_view(created)


@router.post("/manifest/drafts/storybook", status_code=status.HTTP_201_CREATED)
async def draft_from_storybook(
    body: StorybookDraftIn,
    request: Request,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    index = body.index
    if index is None:
        if not body.url:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Give your Storybook's address, or upload its index.json.")
        try:
            index = await drafts.fetch_storybook_index(_safe_url(body.url), fetch_public)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)[:300])
    draft = drafts.draft_from_storybook(index, site_key=site.site_key, docgen=body.docgen)
    return await _save_draft(db, site.site_key, draft, "storybook", _actor(request))


@router.post("/manifest/drafts/site", status_code=status.HTTP_201_CREATED)
async def draft_from_site(
    body: SiteDraftIn,
    request: Request,
    site: store.Website = Depends(owned_website),
    db: AsyncSession = Depends(get_session),
) -> dict:
    raw = body.url or site.domain
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Enter your website's address.")
    try:
        pages = await drafts.fetch_site_pages(_safe_url(raw), fetch_public, body.max_pages)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Could not read the site: {str(exc)[:200]}")
    draft = drafts.draft_from_pages(pages, site_key=site.site_key)
    return await _save_draft(db, site.site_key, draft, "site", _actor(request))
