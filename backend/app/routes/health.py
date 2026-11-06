"""Liveness / readiness probes, and Prometheus metrics (F-3)."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.observability import metrics

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """Every dependency (M3-6): 503 when a critical one fails or the replica
    is draining, so the load balancer sends visitors elsewhere."""
    from app.observability.health import check_all

    rt = request.app.state.runtime
    result = await check_all(request.app)
    body = {
        **result,
        "db": result["checks"]["db"]["ok"],
        "mock_ai": rt.settings.mock_ai,
        "fast_model": rt.settings.fast_model,
        "heavy_model": rt.settings.heavy_model,
    }
    code = 503 if result["status"] in ("fail", "draining") else 200
    return JSONResponse(body, status_code=code, headers={"Cache-Control": "no-store"})


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
