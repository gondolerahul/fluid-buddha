"""
ASGI middleware (F-3): a request id for every request and connection, the
``X-Request-ID`` response header, per-route HTTP metrics, a span per request,
and the open-WebSocket gauge.
"""
from __future__ import annotations

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability import metrics
from app.observability.context import new_request_id, request_id
from app.observability.tracing import set_attribute, span


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers") or []:
        if k.lower() == name:
            try:
                return v.decode("latin-1")
            except Exception:
                return None
    return None


def _route(scope: Scope) -> str:
    route = scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        rid = new_request_id(_header(scope, b"x-request-id"))
        token = request_id.set(rid)
        try:
            if scope["type"] == "websocket":
                metrics.WS_CONNECTIONS.inc()
                try:
                    await self.app(scope, receive, send)
                finally:
                    metrics.WS_CONNECTIONS.dec()
                return
            await self._http(scope, receive, send, rid)
        finally:
            request_id.reset(token)

    async def _http(self, scope: Scope, receive: Receive, send: Send, rid: str) -> None:
        status = 500
        t0 = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        method = scope.get("method", "GET")
        with span("http.request", **{"http.method": method}) as s:
            try:
                await self.app(scope, receive, send_with_id)
            finally:
                route = _route(scope)
                set_attribute(s, "http.route", route)
                set_attribute(s, "http.status_code", status)
                metrics.HTTP_REQUESTS.labels(method, route, f"{status // 100}xx").inc()
                metrics.HTTP_SECONDS.labels(method, route).observe(time.perf_counter() - t0)
