"""
Path-scoped CORS (docs/defects.md D-21).

The public widget surface (``/chat``, ``/widget``, ``/design``, ``/health``) is
embedded on customer sites, so its origin list may be wide open — each request
is still checked against the website's own domain by ``resolve_public_site``.
The admin API (``/auth``, ``/tenant``) only ever serves the console, so it gets
its own, narrow list. One app, two policies, chosen by path prefix.
"""
from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

ADMIN_PREFIXES = ("/auth", "/tenant")


def cors_kwargs(origins: list[str]) -> dict:
    """CORSMiddleware options for an origin list. A credentialed request cannot
    use a wildcard origin (CORS spec), so ``*`` allows any origin with
    credentials off; the console authenticates with a Bearer header, not cookies."""
    wildcard = "*" in origins
    kwargs: dict = {
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "allow_credentials": not wildcard,
        # So browser code can read the id to quote in a bug report (F-3).
        "expose_headers": ["X-Request-ID"],
    }
    if wildcard:
        kwargs["allow_origin_regex"] = r".*"
    else:
        kwargs["allow_origins"] = origins
    return kwargs


class ScopedCORSMiddleware:
    def __init__(self, app: ASGIApp, *, public_origins: list[str],
                 admin_origins: list[str]) -> None:
        self._public = CORSMiddleware(app, **cors_kwargs(public_origins))
        self._admin = CORSMiddleware(app, **cors_kwargs(admin_origins))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else ""
        admin = any(path == p or path.startswith(p + "/") for p in ADMIN_PREFIXES)
        await (self._admin if admin else self._public)(scope, receive, send)
