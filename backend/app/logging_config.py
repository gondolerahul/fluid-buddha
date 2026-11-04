"""Logging setup: readable text by default, JSON lines with ``LOG_FORMAT=json``.
Every line carries the request id of the request that wrote it (F-3)."""
from __future__ import annotations

import logging
import time

from app.observability.context import ContextFilter, JsonFormatter


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    if fmt.strip().lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
        formatter.converter = time.gmtime
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] | %(message)s",
            datefmt="%H:%M:%S",
        )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # cortex_memory is chatty at INFO during ingestion; keep it at WARNING.
    logging.getLogger("cortex_memory").setLevel(logging.WARNING)
