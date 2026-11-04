"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.cors import ScopedCORSMiddleware
from app.db import dispose_engine, init_db
from app.logging_config import configure_logging
from app.routes import (
    agent_profile,
    analytics,
    auth,
    cache,
    chat,
    design,
    health,
    ingestion,
    insights,
    leads,
    onboarding,
    privacy,
    tours,
    websites,
    widget,
)
from app.runtime import build_runtime
from app.transport import websocket as ws_transport
from app.trust.retention import retention_sweep_loop

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("a2ui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.runtime = build_runtime()
    logger.info("A2UI orchestrator ready (mock_ai=%s)", settings.mock_ai)
    # Delete visitor data past each site's retention window (WS8).
    sweep = (asyncio.create_task(retention_sweep_loop(settings.retention_sweep_minutes * 60))
             if settings.retention_sweep_minutes > 0 else None)
    yield
    if sweep:
        sweep.cancel()
    await dispose_engine()


app = FastAPI(title="A2UI Orchestrator", version="0.1.0", lifespan=lifespan)

# The public widget and the admin API share this app but not a CORS policy:
# CORS_ORIGINS covers the widget surface, ADMIN_CORS_ORIGINS the console-only
# /auth + /tenant routes (docs/defects.md D-21).
app.add_middleware(
    ScopedCORSMiddleware,
    public_origins=settings.cors_origin_list,
    admin_origins=settings.admin_cors_origin_list,
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(design.router)
app.include_router(ws_transport.router)
app.include_router(widget.router)
app.include_router(leads.public)

# Admin dashboard API (tenant auth + website management; more in later phases).
app.include_router(auth.router)
app.include_router(websites.router)
app.include_router(ingestion.router)
app.include_router(tours.router)
app.include_router(cache.router)
app.include_router(analytics.router)
app.include_router(agent_profile.router)
app.include_router(insights.router)
app.include_router(leads.admin)
app.include_router(privacy.router)
app.include_router(onboarding.router)
