"""
Security headers on every response (M2-11).

* ``X-Content-Type-Options: nosniff`` and ``Referrer-Policy`` everywhere;
* ``X-Frame-Options: DENY`` + ``frame-ancestors 'none'`` — nothing this server
  returns is meant to be framed (recap pages set their own, stricter CSP);
* ``Cache-Control: no-store`` on the console API (``/auth``, ``/tenant``), whose
  answers are account data;
* ``Strict-Transport-Security`` outside dev.

A header a route set itself is left alone.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_PRIVATE = ("/auth", "/tenant")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        private = any(path == p or path.startswith(p + "/") for p in _PRIVATE)

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                have = {k.lower() for k, _ in headers}

                def add(name: bytes, value: bytes) -> None:
                    if name not in have:
                        headers.append((name, value))

                add(b"x-content-type-options", b"nosniff")
                add(b"referrer-policy", b"strict-origin-when-cross-origin")
                add(b"x-frame-options", b"DENY")
                if b"content-security-policy" not in have:
                    headers.append((b"content-security-policy", b"frame-ancestors 'none'"))
                if private:
                    add(b"cache-control", b"no-store")
                if self.hsts:
                    add(b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped)
