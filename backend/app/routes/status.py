"""
The public status page (M3-6).

    GET  /status                          the page (no sign-in)
    GET  /status.json                     the same, as JSON
    POST /status/incidents                open an incident or schedule maintenance
    POST /status/incidents/{id}/updates   post an update (``resolved`` closes it)

Posting needs ``Authorization: Bearer $STATUS_TOKEN`` (unset = no posting): the
on-call engineer does it from the incident runbook, not a customer account.
"""
from __future__ import annotations

import hmac
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import get_settings
from app.db import session_scope
from app.status import page
from app.status import store

router = APIRouter(tags=["status"])

_HEADERS = {"Cache-Control": "public, max-age=30", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"}


@router.get("/status", response_class=HTMLResponse, include_in_schema=False)
async def status_page() -> HTMLResponse:
    async with session_scope() as db:
        s = await store.summary(db)
    return HTMLResponse(page.render(s, title=get_settings().status_title), headers=_HEADERS)


@router.get("/status.json")
async def status_json() -> JSONResponse:
    async with session_scope() as db:
        s = await store.summary(db)
    return JSONResponse(s, headers={**_HEADERS, "Access-Control-Allow-Origin": "*"})


def _operator(request: Request) -> None:
    token = get_settings().status_token
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    sent = request.headers.get("authorization", "")
    if not hmac.compare_digest(sent.encode(), f"Bearer {token}".encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})


@router.post("/status/incidents", status_code=status.HTTP_201_CREATED)
async def open_incident(body: dict, request: Request) -> dict:
    _operator(request)
    async with session_scope() as db:
        try:
            return await store.open_incident(db, body)
        except store.StatusError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("/status/incidents/{incident_id}/updates")
async def update_incident(incident_id: uuid.UUID, body: dict, request: Request) -> dict:
    _operator(request)
    async with session_scope() as db:
        try:
            out = await store.add_update(db, incident_id, body)
        except store.StatusError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such incident")
    return out
