"""
The installed licence, and what it allows (M3-5). Only when ``SELF_HOSTED``.

Where the licence comes from, first found wins: the one installed in the
console (``install_licence``), ``LICENCE_KEY``, the file at ``LICENCE_FILE``.
It is read at most once a minute, and again right after the console installs
one.

What it guards (console paths only; visitors are never affected):

* past the grace period, missing or invalid → ``/tenant`` changes are refused
  (402), except installing a licence; reading still works;
* features the licence doesn't include → those routes are refused (402);
* new websites beyond ``sites`` and new team members beyond ``seats``, counted
  across the whole install → refused (402).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings
from app.licence import core

logger = logging.getLogger(__name__)

_TTL_S = 60.0
_cache: dict[str, Any] = {"at": 0.0, "lic": None, "error": None, "source": None}

READ = {"GET", "HEAD", "OPTIONS"}
ALWAYS_ALLOWED = re.compile(r"^/tenant/licence$")
FEATURE_PATHS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/tenant/model-provider|^/tenant/websites/[^/]+/model$"), "byo_model"),
    (re.compile(r"^/tenant/websites/[^/]+/agent-(access|tokens)"), "agent_access"),
    (re.compile(r"^/tenant/websites/[^/]+/campaigns"), "campaigns"),
    (re.compile(r"^/tenant/sso|^/auth/sso"), "sso"),
]
EXPIRED_MESSAGE = ("This install's FluidBuddha licence has expired, so the console is read-only. Visitors aren't "
                   "affected. An Owner can install a new licence under Account → Licence.")


def enabled() -> bool:
    return bool(get_settings().self_hosted)


async def _load(db: Optional[AsyncSession]) -> tuple[Optional[str], Optional[str]]:
    """The token and where it came from."""
    if db is not None:
        try:
            row = (await db.execute(text("SELECT token FROM install_licence WHERE id = 1"))).first()
            if row and row[0]:
                return row[0], "console"
        except Exception as exc:   # the table may not exist yet during a first migration
            logger.debug("licence table unavailable: %s", exc)
    s = get_settings()
    if s.licence_key:
        return s.licence_key, "env"
    if s.licence_file:
        try:
            return Path(s.licence_file).read_text(encoding="utf-8").strip(), "file"
        except OSError as exc:
            logger.warning("licence file %s unreadable: %s", s.licence_file, exc)
    return None, None


async def refresh(db: Optional[AsyncSession] = None) -> None:
    from app.db import session_scope

    if db is None:
        async with session_scope() as own:
            token, source = await _load(own)
    else:
        token, source = await _load(db)
    lic, error = None, None
    if token:
        try:
            lic = core.parse(token)
        except core.LicenceError as exc:
            error = exc.reason
    _cache.update(at=time.monotonic(), lic=lic, error=error, source=source)


async def current() -> dict[str, Any]:
    """The licence's state now (cached for a minute)."""
    if time.monotonic() - _cache["at"] > _TTL_S:
        try:
            await refresh()
        except Exception as exc:
            logger.warning("licence check failed: %s", exc)
    out = core.state(_cache["lic"], error=_cache["error"])
    out["source"] = _cache["source"]
    return out


def licence() -> Optional[core.Licence]:
    return _cache["lic"]


async def check_limit(db: AsyncSession, kind: str) -> None:
    """Refuse a new website or team member beyond the licence (install-wide)."""
    if not enabled():
        return
    st = await current()
    lic = _cache["lic"]
    if not st["usable"] or lic is None:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, EXPIRED_MESSAGE)
    if kind == "sites":
        used = (await db.execute(text("SELECT count(*) FROM tenant_websites"))).scalar() or 0
        if used >= lic.sites:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                                f"This install's licence covers {lic.sites} website{'s' if lic.sites != 1 else ''}, "
                                "and they're all in use.")
    elif kind == "seats":
        used = (await db.execute(text(
            "SELECT (SELECT count(DISTINCT user_id) FROM memberships) + (SELECT count(*) FROM invitations "
            "WHERE accepted_at IS NULL AND expires_at > now())"))).scalar() or 0
        if used >= lic.seats:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                                f"This install's licence covers {lic.seats} team seat{'s' if lic.seats != 1 else ''}, "
                                "and they're all taken (pending invitations count).")


class LicenceGuard:
    """Console changes need a usable licence; licensed features need the feature."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not enabled() or not path.startswith(("/tenant/", "/auth/sso")):
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET").upper()
        if method != "OPTIONS" and not ALWAYS_ALLOWED.match(path):
            st = await current()
            lic = _cache["lic"]
            reason = None
            if not st["usable"] and method not in READ:
                reason = EXPIRED_MESSAGE
            elif lic is not None:
                for rx, feature in FEATURE_PATHS:
                    if rx.search(path) and not lic.has(feature):
                        reason = f"This install's licence doesn't include this feature ({feature})."
                        break
            if reason:
                await JSONResponse({"detail": reason, "licence": st["state"]}, status_code=402)(scope, receive, send)
                return
        await self.app(scope, receive, send)
