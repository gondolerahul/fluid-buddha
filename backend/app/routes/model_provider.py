"""
Bring your own model — console API (M3-4). Owners and Admins only (the key
is the account's own contract with a provider); every change audit-logged.

    GET    /tenant/model-provider            the account's provider (never the key)
    PUT    /tenant/model-provider            {provider, fast_model, thinker_model,
                                              api_key?, endpoint?, api_version?,
                                              prices?, enabled}
    DELETE /tenant/model-provider            back to the platform's model
    POST   /tenant/model-provider/test       a one-line round trip with each model
    PUT    /tenant/websites/{id}/model       {byo_model}: this site on the account's
                                              provider or the platform's
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import providers
from app.auth import team
from app.auth.security import current_member
from app.db import get_session
from app.security import secrets as stored
from app.tenancy import store as tenancy
from app.tenancy.deps import owned_website

router = APIRouter(prefix="/tenant", tags=["model-provider"])

_MODEL = re.compile(r"^[A-Za-z0-9._:/@-]{1,120}$")


class Price(BaseModel):
    model_config = {"populate_by_name": True}
    in_: Optional[float] = Field(None, ge=0, le=1000, alias="in")
    out: Optional[float] = Field(None, ge=0, le=1000)


class ProviderIn(BaseModel):
    provider: Literal["anthropic", "openai", "azure_openai"]
    fast_model: str = Field(..., max_length=120)
    thinker_model: str = Field(..., max_length=120)
    api_key: Optional[str] = Field(None, max_length=500)       # omit to keep the stored one
    endpoint: Optional[str] = Field(None, max_length=300)
    api_version: Optional[str] = Field(None, max_length=40)
    prices: dict[Literal["fast", "thinker"], Price] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("fast_model", "thinker_model")
    @classmethod
    def _model(cls, v: str) -> str:
        v = v.strip()
        if not _MODEL.match(v):
            raise ValueError("a model (or Azure deployment) name, like claude-opus-5-5")
        return v

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        parts = urlsplit(v.strip())
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError("your Azure OpenAI endpoint, like https://my-resource.openai.azure.com")
        return f"https://{parts.netloc}"


def _public(row: Any) -> dict:
    prices = row["prices"] if isinstance(row["prices"], dict) else json.loads(row["prices"] or "{}")
    return {
        "configured": True, "provider": row["provider"], "fast_model": row["fast_model"],
        "thinker_model": row["thinker_model"], "endpoint": row["endpoint"],
        "api_version": row["api_version"], "prices": prices, "enabled": row["enabled"],
        "key_hint": row["key_hint"],
        "last_test_at": row["last_test_at"].isoformat() if row["last_test_at"] else None,
        "last_test_ok": row["last_test_ok"], "last_error": row["last_error"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def _row(db: AsyncSession, tenant_id) -> Optional[Any]:
    row = (await db.execute(text(
        "SELECT * FROM model_providers WHERE tenant_id = :t"), {"t": tenant_id})).mappings().first()
    if not row:
        return None
    out = dict(row)
    key = stored.decrypt(row["api_key_enc"])
    out["key_hint"] = f"…{key[-4:]}" if len(key) >= 8 else "set"
    return out


@router.get("/model-provider")
async def get_provider(m: team.Member = Depends(current_member),
                       db: AsyncSession = Depends(get_session)) -> dict:
    row = await _row(db, m.tenant.id)
    sites = (await db.execute(text(
        "SELECT id, name, byo_model FROM tenant_websites WHERE tenant_id = :t ORDER BY created_at"),
        {"t": m.tenant.id})).mappings().all()
    return {**(_public(row) if row else {"configured": False}),
            "defaults": {k: {"fast_model": f, "thinker_model": t}
                         for k, (f, t) in providers.DEFAULT_MODELS.items()},
            "list_prices": {k: {"in": v[0], "out": v[1]} for k, v in providers.LIST_PRICES.items()},
            "sites": [{"id": str(s["id"]), "name": s["name"], "byo_model": s["byo_model"]} for s in sites]}


@router.put("/model-provider")
async def put_provider(body: ProviderIn, m: team.Member = Depends(current_member),
                       db: AsyncSession = Depends(get_session)) -> dict:
    current = await _row(db, m.tenant.id)
    key = (body.api_key or "").strip()
    if not key and not current:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Paste the API key for this provider.")
    if current and current["provider"] != body.provider and not key:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "A different provider needs its own API key.")
    if body.provider == "azure_openai" and not body.endpoint:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Azure OpenAI needs your resource's endpoint.")
    enc = stored.encrypt(key) if key else current["api_key_enc"]
    prices = {role: {"in": p.in_, "out": p.out} for role, p in body.prices.items()}
    await db.execute(text(
        "INSERT INTO model_providers (tenant_id, provider, fast_model, thinker_model, api_key_enc, endpoint, "
        "api_version, prices, enabled, updated_at) VALUES (:t, :p, :f, :th, :k, :e, :v, CAST(:pr AS jsonb), "
        ":en, now()) ON CONFLICT (tenant_id) DO UPDATE SET provider = :p, fast_model = :f, thinker_model = :th, "
        "api_key_enc = :k, endpoint = :e, api_version = :v, prices = CAST(:pr AS jsonb), enabled = :en, "
        "updated_at = now(), last_test_at = NULL, last_test_ok = NULL, last_error = NULL"),
        {"t": m.tenant.id, "p": body.provider, "f": body.fast_model, "th": body.thinker_model, "k": enc,
         "e": body.endpoint if body.provider == "azure_openai" else None,
         "v": (body.api_version or "").strip() or None, "pr": json.dumps(prices), "en": body.enabled})
    await db.commit()
    providers.forget(m.tenant.id)
    return _public(await _row(db, m.tenant.id))


@router.delete("/model-provider", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(m: team.Member = Depends(current_member),
                          db: AsyncSession = Depends(get_session)) -> None:
    await db.execute(text("DELETE FROM model_providers WHERE tenant_id = :t"), {"t": m.tenant.id})
    await db.commit()
    providers.forget(m.tenant.id)


@router.post("/model-provider/test")
async def test_provider(m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> dict:
    row = await _row(db, m.tenant.id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set up a provider first.")
    cfg = providers.ProviderConfig(
        tenant_id=m.tenant.id, provider=row["provider"], fast_model=row["fast_model"],
        thinker_model=row["thinker_model"], api_key=stored.decrypt(row["api_key_enc"]),
        endpoint=row["endpoint"], api_version=row["api_version"])
    client = providers.build_client(
        cfg, http_client=providers.http_client_factory(cfg.provider) if providers.http_client_factory else None)
    results, error = [], None
    for role, model in (("fast", cfg.fast_model), ("thinker", cfg.thinker_model)):
        try:
            answered = await client.check(model)
            results.append({"role": role, "model": model, "ok": True, "answered_by": answered})
        except Exception as exc:
            msg = f"{type(exc).__name__}: {getattr(exc, 'message', None) or exc}"[:300]
            results.append({"role": role, "model": model, "ok": False, "error": msg})
            error = error or f"{role} model {model}: {msg}"
    await db.execute(text(
        "UPDATE model_providers SET last_test_at = now(), last_test_ok = :ok, last_error = :e "
        "WHERE tenant_id = :t"), {"ok": error is None, "e": error, "t": m.tenant.id})
    await db.commit()
    return {"ok": error is None, "results": results}


class SiteModelIn(BaseModel):
    byo_model: bool


@router.put("/websites/{website_id}/model")
async def site_model(body: SiteModelIn, site: tenancy.Website = Depends(owned_website),
                     db: AsyncSession = Depends(get_session)) -> dict:
    await db.execute(text("UPDATE tenant_websites SET byo_model = :b WHERE id = :id"),
                     {"b": body.byo_model, "id": site.id})
    await db.commit()
    providers.forget(site.tenant_id)
    return {"id": str(site.id), "byo_model": body.byo_model}
