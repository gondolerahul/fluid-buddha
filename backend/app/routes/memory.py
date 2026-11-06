"""
Returning-visitor memory — the widget's side (M3-3).

    POST /memory   {key, visitor, remember: true}   "Remember me": opt in
                   {key, visitor, remember: false}  "Forget me": delete it all

The site must offer memory (Privacy settings). Key and domain are checked
like every public call; JSON sent as text/plain is fine (sendBeacon).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.db import session_scope
from app.memory import store as memory
from app.routes.experiments import _body
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.transport import guard

router = APIRouter(tags=["memory"])


@router.post("/memory")
async def set_memory(request: Request) -> dict:
    data = await _body(request)
    visitor = memory.valid_visitor(data.get("visitor"))
    if not visitor:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid visitor id")
    async with session_scope() as db:
        try:
            resolved = await resolve_public_site(db, key=data.get("key"), site=data.get("site"),
                                                 intelligence=None, origin=request.headers.get("origin"))
        except PublicAccessError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, exc.reason)
        if resolved.website is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory isn't offered here")
        if not guard._limiter.allow(f"memory:{resolved.site_key}:{visitor}", 10):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, guard.RATE_LIMITED)
        if data.get("remember") is True:
            if not await memory.enabled(db, resolved.site_key):
                raise HTTPException(status.HTTP_409_CONFLICT, "Memory isn't offered here")
            await memory.opt_in(db, resolved.site_key, visitor)
            await db.commit()
            return {"remembered": True}
        forgotten = await memory.forget(db, resolved.site_key, visitor)
        await db.commit()
    return {"remembered": False, "forgotten": forgotten}
