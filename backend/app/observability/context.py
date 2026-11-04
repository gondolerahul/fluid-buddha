"""
Per-request context for logs (F-3).

Every HTTP request and WebSocket connection gets a request id (the caller's
``X-Request-ID`` if it sent a sane one, else a fresh one). It is returned in the
response header and stamped on every log line written while handling it, so a
support ticket's id leads straight to the logs. A voice connection also carries
its session id.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar
from typing import Optional

request_id: ContextVar[str] = ContextVar("request_id", default="-")
session_id: ContextVar[str] = ContextVar("session_id", default="-")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def new_request_id(incoming: Optional[str] = None) -> str:
    """Trust the caller's id only when it is short and plain (no log injection)."""
    if incoming and _SAFE_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        record.session_id = session_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, for log shippers (``LOG_FORMAT=json``)."""

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        sid = getattr(record, "session_id", "-")
        if sid != "-":
            out["session_id"] = sid
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)
