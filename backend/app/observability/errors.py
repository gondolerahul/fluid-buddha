"""
Optional Sentry error reporting (F-3).

Off unless ``SENTRY_DSN`` is set and ``sentry-sdk`` is installed. Events are
scrubbed before they leave: no request bodies (they carry what visitors typed),
no cookies, query strings or auth headers, no user, and no local variables in
stack frames (they can hold transcripts). Each event is tagged with the request
id, so it matches the log lines of the same request.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.observability.context import request_id

logger = logging.getLogger(__name__)

_KEEP_HEADERS = {"user-agent", "content-type", "content-length", "x-request-id", "origin"}


def scrub(event: dict, hint: Optional[dict] = None) -> dict:
    req = event.get("request")
    if isinstance(req, dict):
        for key in ("data", "cookies", "query_string", "env"):
            req.pop(key, None)
        headers = req.get("headers")
        if isinstance(headers, dict):
            req["headers"] = {k: v for k, v in headers.items() if k.lower() in _KEEP_HEADERS}
    event.pop("user", None)
    for exc in (event.get("exception") or {}).get("values") or []:
        for frame in (exc.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    for crumb in (event.get("breadcrumbs") or {}).get("values") or []:
        crumb.pop("data", None)
    rid = request_id.get()
    if rid != "-":
        event.setdefault("tags", {})["request_id"] = rid
    return event


def setup_sentry(settings, *, transport: Any = None) -> bool:
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk isn't installed "
                       "(pip install -r requirements-observability.txt)")
        return False
    kwargs: dict = {}
    if transport is not None:
        kwargs["transport"] = transport
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.app_env,
        release=settings.release or None,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,   # tracing goes through OpenTelemetry instead
        before_send=scrub,
        **kwargs,
    )
    logger.info("error reporting on (Sentry, environment=%s)", settings.app_env)
    return True
