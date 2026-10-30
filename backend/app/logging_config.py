"""Minimal structured-ish logging setup."""
from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # cortex_memory is chatty at INFO during ingestion; keep it at WARNING.
    logging.getLogger("cortex_memory").setLevel(logging.WARNING)
