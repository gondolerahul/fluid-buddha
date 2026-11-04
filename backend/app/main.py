"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.audit import AuditMiddleware
from app.config import get_settings
from app.cors import ScopedCORSMiddleware
from app.db import dispose_engine, init_db
from app.logging_config import configure_logging
from app.observability.errors import setup_sentry
from app.observability.middleware import ObservabilityMiddleware
from app.observability.tracing import setup_tracing
from app.routes import (
    agent_profile,
    analytics,
    auth,
    billing,
    cache,
    chat,
    design,
    experiments,
    health,
    ingestion,
    insights,
    leads,
    onboarding,
    privacy,
    team,
    tours,
    websites,
    widget,
)
from app.runtime import build_runtime
from app.transport import websocket as ws_transport
from app.jobs import build_scheduler

settings = get_settings()
configure_logging(settings.log_level, settings.log_format)
logger = logging.getLogger("a2ui")
# Both are no-ops unless configured (SENTRY_DSN, OTEL_EXPORTER_OTLP_ENDPOINT).
setup_sentry(settings)
setup_tracing(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.runtime = build_runtime()
    logger.info("A2UI orchestrator ready (mock_ai=%s)", settings.mock_ai)
    # Periodic jobs (M2-0): retention sweep (WS8), email outbox, …
    scheduler = build_scheduler(settings)
    scheduler.start()
    yield
    await scheduler.stop()
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
# Every successful change made through /tenant routes goes in the audit log (M2-1).
app.add_middleware(AuditMiddleware)
# Outermost: every response (CORS preflights included) gets an X-Request-ID,
# and every log line written while handling it carries that id (F-3).
app.add_middleware(ObservabilityMiddleware)

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
app.include_router(experiments.public)
app.include_router(experiments.admin)
app.include_router(billing.admin)
app.include_router(billing.webhooks)
app.include_router(team.router)
