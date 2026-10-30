"""Liveness / readiness probes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db import engine

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
