"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_engine, init_db
from app.logging_config import configure_logging
from app.routes import (
    analytics,
    auth,
    cache,
    chat,
    design,
    health,
    ingestion,
    tours,
    websites,
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

# A credentialed request cannot use a wildcard origin (CORS spec), and an
# allow-all origin is too broad for the admin API that shares this app. The
# console authenticates with a Bearer token (not cookies), so when origins are
# left wide open we allow any origin but turn credentials off. Set an explicit
# CORS_ORIGINS list in any deployed environment. See docs/defects.md D-21.
wildcard = "*" in settings.cors_origin_list or settings.cors_origins.strip() == "*"
cors_kwargs = {
    "allow_methods": ["*"],
    "allow_headers": ["*"],
    "allow_credentials": not wildcard,
}
if wildcard:
    cors_kwargs["allow_origin_regex"] = r".*"
else:
    cors_kwargs["allow_origins"] = settings.cors_origin_list

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(design.router)
app.include_router(ws_transport.router)

# Admin dashboard API (tenant auth + website management; more in later phases).
app.include_router(auth.router)
app.include_router(websites.router)
app.include_router(ingestion.router)
app.include_router(tours.router)
app.include_router(cache.router)
app.include_router(analytics.router)
