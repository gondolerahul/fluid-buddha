"""
Prometheus metrics (F-3), served at ``/metrics``.

Labels are deliberately coarse — route templates, stages, outcomes — never site
keys, visitors or paths with ids, so cardinality stays bounded and a scrape
reveals nothing about tenants. Per-site numbers live in the Analytics tab.

The one the product cares most about is **time to first audio**: from the
moment a visitor's question reaches the server to the first byte of speech sent
back (usually the router's short ack), and separately to the first byte of the
answer itself.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import (
    CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8, 13, 20, 30)

HTTP_REQUESTS = Counter(
    "fb_http_requests_total", "HTTP requests by route template and status class.",
    ["method", "route", "status"], registry=REGISTRY,
)
HTTP_SECONDS = Histogram(
    "fb_http_request_seconds", "HTTP request duration by route template.",
    ["method", "route"], buckets=_LATENCY_BUCKETS, registry=REGISTRY,
)
WS_CONNECTIONS = Gauge(
    "fb_ws_connections", "Open voice WebSocket connections.", registry=REGISTRY,
)
TURNS = Counter(
    "fb_turns_total", "Answered visitor turns.", ["channel", "path"], registry=REGISTRY,
)
TURN_SECONDS = Histogram(
    "fb_turn_seconds", "Whole-turn duration, question in to last byte out.",
    ["channel", "path"], buckets=_LATENCY_BUCKETS, registry=REGISTRY,
)
FIRST_AUDIO_SECONDS = Histogram(
    "fb_time_to_first_audio_seconds",
    "Question received to the first byte of speech sent (usually the ack).",
    ["path"], buckets=_LATENCY_BUCKETS, registry=REGISTRY,
)
FIRST_ANSWER_AUDIO_SECONDS = Histogram(
    "fb_time_to_first_answer_audio_seconds",
    "Question received to the first byte of the answer's speech.",
    ["path"], buckets=_LATENCY_BUCKETS, registry=REGISTRY,
)
STAGE_SECONDS = Histogram(
    "fb_stage_seconds", "Duration of one stage of a turn.",
    ["stage"], buckets=_LATENCY_BUCKETS, registry=REGISTRY,
)
ENGINE_ERRORS = Counter(
    "fb_engine_errors_total", "Failures in an AI engine call.", ["engine"], registry=REGISTRY,
)
CRAWL_JOBS = Counter(
    "fb_crawl_jobs_total", "Website crawl jobs by outcome.", ["status"], registry=REGISTRY,
)
JOB_RUNS = Counter(
    "fb_job_runs_total", "Background job runs by outcome (ok, error, skipped = another replica).",
    ["job", "outcome"], registry=REGISTRY,
)
COST_ALERTS = Counter(
    "fb_cost_alerts_total", "Per-site daily cost alerts raised (threshold, cap_80, cap_100).",
    ["level"], registry=REGISTRY,
)


@contextmanager
def timed(stage: str) -> Iterator[None]:
    """Time a turn stage into ``fb_stage_seconds`` and a tracing span."""
    from app.observability.tracing import span

    t0 = time.perf_counter()
    with span(f"stage.{stage}"):
        try:
            yield
        finally:
            STAGE_SECONDS.labels(stage).observe(time.perf_counter() - t0)


def render() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
