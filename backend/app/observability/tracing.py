"""
Optional OpenTelemetry tracing (F-3).

Off unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set and the OpenTelemetry
packages are installed (``requirements-observability.txt``). When on, every
HTTP request and voice turn is a span, with child spans for its stages
(router, retrieval, thinker, speech synthesis, replay), exported over OTLP/HTTP
to the collector at that endpoint. When off, ``span()`` costs nothing.

Span attributes never include what visitors said or typed.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

_tracer: Optional[Any] = None


def setup_tracing(settings, *, exporter: Any = None) -> bool:
    """Start exporting spans. ``exporter`` overrides OTLP (tests)."""
    global _tracer
    endpoint = (settings.otel_exporter_otlp_endpoint or "").strip()
    if not endpoint and exporter is None:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    except ImportError:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT is set but OpenTelemetry isn't "
                       "installed (pip install -r requirements-observability.txt)")
        return False
    provider = TracerProvider(resource=Resource.create({
        "service.name": settings.otel_service_name,
        "deployment.environment": settings.app_env,
    }))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
    _tracer = provider.get_tracer("fluid-buddha")
    if exporter is None:
        trace.set_tracer_provider(provider)
    logger.info("tracing on: exporting spans to %s", endpoint or "a test exporter")
    return True


def disable_tracing() -> None:
    global _tracer
    _tracer = None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Optional[Any]]:
    if _tracer is None:
        with nullcontext() as nothing:
            yield nothing
        return
    with _tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            if v is not None:
                s.set_attribute(k, v)
        yield s


def set_attribute(current: Optional[Any], key: str, value: Any) -> None:
    if current is not None and value is not None:
        current.set_attribute(key, value)
