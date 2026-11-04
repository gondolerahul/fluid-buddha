"""Liveness / readiness probes, and Prometheus metrics (F-3)."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.observability import metrics

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict:
    rt = request.app.state.runtime
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "mock_ai": rt.settings.mock_ai,
        "fast_model": rt.settings.fast_model,
        "heavy_model": rt.settings.heavy_model,
    }


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request) -> Response:
    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404)
    token = settings.metrics_token
    if token:
        sent = request.headers.get("authorization", "")
        if not hmac.compare_digest(sent.encode(), f"Bearer {token}".encode()):
            raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)
