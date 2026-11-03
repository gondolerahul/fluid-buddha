"""FastAPI application entrypoint."""
from __future__ import annotations

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
    tours,
    websites,
    widget,
)
from app.runtime import build_runtime
from app.transport import websocket as ws_transport

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("a2ui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.runtime = build_runtime()
    logger.info("A2UI orchestrator ready (mock_ai=%s)", settings.mock_ai)
    yield
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

# Admin dashboard API (tenant auth + website management; more in later phases).
app.include_router(auth.router)
app.include_router(websites.router)
app.include_router(ingestion.router)
app.include_router(tours.router)
app.include_router(cache.router)
app.include_router(analytics.router)
app.include_router(agent_profile.router)
app.include_router(insights.router)
