"""
Live takeover for the console (M2-2). Reads need Viewer; taking over,
messaging, handing back and calling need Editor (the central role rules), and
every one of those changes lands in the audit log.

    GET  /tenant/live                                    who's on your sites now
    GET  /tenant/live/ice                                relay servers for a call
    GET  /tenant/websites/{id}/live/{session}            conversation so far
    POST /tenant/websites/{id}/live/{session}/takeover
    POST /tenant/websites/{id}/live/{session}/message    {text}
    POST /tenant/websites/{id}/live/{session}/release
    POST /tenant/websites/{id}/live/{session}/call       {type: offer|ice|hangup, sdp?, candidate?}
    WS   /tenant/live/events    first message {"token": "<console token>"}; then
                                a snapshot and every event on your sites
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Literal, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import team
from app.auth.security import current_member, decode_token
from app.db import get_session, session_scope
from app.live import store as live
from app.live.bus import bus, session_topic, site_topic
from app.live.turn import ice_servers
from app.tenancy import store
from app.tenancy.deps import owned_website

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenant", tags=["live"])


async def _sites(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, dict]:
    rows = (await db.execute(text(
        "SELECT id, site_key, name FROM tenant_websites WHERE tenant_id = :t"),
        {"t": tenant_id})).mappings().all()
    return {r["site_key"]: {"website_id": str(r["id"]), "website_name": r["name"]} for r in rows}


@router.get("/live")
async def live_now(m: team.Member = Depends(current_member),
                   db: AsyncSession = Depends(get_session)) -> list[dict]:
    sites = await _sites(db, m.tenant.id)
    return [{**s, **sites[s["site_key"]]} for s in await live.live_sessions(db, list(sites))]


@router.get("/live/ice")
async def live_ice(m: team.Member = Depends(current_member)) -> dict:
    return {"ice_servers": ice_servers(f"op-{m.user_id.hex[:12]}")}


@router.get("/websites/{website_id}/live/{session_id}")
async def live_conversation(session_id: str, site: store.Website = Depends(owned_website),
                            db: AsyncSession = Depends(get_session)) -> dict:
    turns = (await db.execute(text(
        "SELECT t.question, t.answer, t.created_at FROM conversation_turns t "
        "JOIN conversations c ON c.id = t.conversation_id "
        "WHERE c.site_key = :s AND c.session_id = :sid ORDER BY t.created_at"),
        {"s": site.site_key, "sid": session_id})).mappings().all()
    events: list[dict[str, Any]] = []
    for t in turns:
        events.append({"sender": "visitor", "text": t["question"], "at": t["created_at"].isoformat()})
        events.append({"sender": "agent", "text": t["answer"], "at": t["created_at"].isoformat()})
    events += await live.messages(db, site.site_key, session_id)
    events.sort(key=lambda e: e["at"])
    tk = await live.active(db, site.site_key, session_id)
    return {"session_id": session_id, "live": await live.is_live(db, site.site_key, session_id),
            "takeover": tk.public() if tk else None, "events": events}


def _name(m: team.Member) -> str:
    return m.name or m.email.split("@")[0]


async def _held_by(db: AsyncSession, site_key: str, session_id: str,
                   m: team.Member) -> live.Takeover:
    tk = await live.active(db, site_key, session_id)
    if tk is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Take over the conversation first.")
    if tk.operator_user_id != m.user_id:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{tk.operator_name} has this conversation.")
    return tk


@router.post("/websites/{website_id}/live/{session_id}/takeover")
async def take_over(session_id: str, site: store.Website = Depends(owned_website),
                    m: team.Member = Depends(current_member),
                    db: AsyncSession = Depends(get_session)) -> dict:
    if not await live.is_live(db, site.site_key, session_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That visitor has left.")
    tk = await live.start(db, site.site_key, session_id, operator_user_id=m.user_id,
                          operator_name=_name(m))
    if tk is None:
        holder = await live.active(db, site.site_key, session_id)
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{holder.operator_name if holder else 'Someone'} already has this "
                            "conversation.")
    await live.add_message(db, site.site_key, session_id, "system", f"{tk.operator_name} joined")
    await db.commit()
    event = {"session_id": session_id, "operator_name": tk.operator_name,
             "operator_user_id": str(m.user_id)}
    await bus.publish(session_topic(site.site_key, session_id), {"type": "takeover_started", **event})
    await bus.publish(site_topic(site.site_key), {"type": "takeover_started", **event})
    return tk.public()


class MessageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


@router.post("/websites/{website_id}/live/{session_id}/message")
async def send_message(session_id: str, body: MessageIn,
                       site: store.Website = Depends(owned_website),
                       m: team.Member = Depends(current_member),
                       db: AsyncSession = Depends(get_session)) -> dict:
    tk = await _held_by(db, site.site_key, session_id, m)
    msg = await live.add_message(db, site.site_key, session_id, "operator", body.text.strip(),
                                 author=tk.operator_name)
    await db.commit()
    await bus.publish(session_topic(site.site_key, session_id), {
        "type": "operator_message", "operator_name": tk.operator_name, "text": msg["text"],
        "id": msg["id"]})
    await bus.publish(site_topic(site.site_key), {
        "type": "operator_message", "session_id": session_id, "message": msg})
    return msg


@router.post("/websites/{website_id}/live/{session_id}/release")
async def release(session_id: str, site: store.Website = Depends(owned_website),
                  m: team.Member = Depends(current_member),
                  db: AsyncSession = Depends(get_session)) -> dict:
    tk = await live.active(db, site.site_key, session_id)
    if tk is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nobody has this conversation.")
    # The holder hands back; an Admin may take it off someone who walked away.
    if tk.operator_user_id != m.user_id and m.role not in ("admin", "owner"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{tk.operator_name} has this conversation.")
    await live.end(db, site.site_key, session_id)
    await live.add_message(db, site.site_key, session_id, "system",
                           f"{tk.operator_name} handed back to the agent")
    await db.commit()
    event = {"session_id": session_id, "operator_name": tk.operator_name}
    await bus.publish(session_topic(site.site_key, session_id), {"type": "takeover_ended", **event})
    await bus.publish(site_topic(site.site_key), {"type": "takeover_ended", **event})
    return {"released": True}


class CallIn(BaseModel):
    type: Literal["offer", "ice", "hangup"]
    sdp: Optional[str] = Field(None, max_length=20_000)
    candidate: Optional[dict] = None


@router.post("/websites/{website_id}/live/{session_id}/call")
async def call_signal(session_id: str, body: CallIn,
                      site: store.Website = Depends(owned_website),
                      m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> dict:
    """WebRTC signalling towards the visitor. Only the person holding the
    conversation can call; the visitor must accept in the widget."""
    tk = await _held_by(db, site.site_key, session_id, m)
    event: dict[str, Any] = {"type": f"call_{body.type}", "operator_name": tk.operator_name}
    if body.type == "offer":
        if not body.sdp:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "An offer needs its SDP.")
        event["sdp"] = body.sdp
        event["ice_servers"] = ice_servers(f"v-{session_id[:12]}")
        await live.add_message(db, site.site_key, session_id, "system",
                               f"{tk.operator_name} asked to talk by voice")
        await db.commit()
    elif body.type == "ice":
        event["candidate"] = body.candidate
    await bus.publish(session_topic(site.site_key, session_id), event)
    return {"sent": True}


# ---- the console's event socket ----------------------------------------------------

async def _authenticate(ws: WebSocket) -> Optional[team.Member]:
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10)
        token = json.loads(first).get("token", "")
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tid"]) if payload.get("tid") else None
    except (asyncio.TimeoutError, ValueError, KeyError, jwt.PyJWTError, WebSocketDisconnect):
        return None
    async with session_scope() as db:
        return await team.member(db, user_id, tenant_id)


@router.websocket("/live/events")
async def live_events(ws: WebSocket) -> None:
    """Every live event on the account's sites, for the console's inbox. The
    token comes in the first message (not the URL, which ends up in logs)."""
    await ws.accept()
    m = await _authenticate(ws)
    if m is None:
        await ws.send_json({"type": "error", "reason": "not_authenticated"})
        await ws.close(code=4401)
        return
    async with session_scope() as db:
        sites = await _sites(db, m.tenant.id)
        sessions = await live.live_sessions(db, list(sites))
    await ws.send_json({"type": "snapshot", "sessions": [
        {**s, **sites[s["site_key"]]} for s in sessions]})
    topics = [site_topic(k) for k in sites]

    async def pump(q: asyncio.Queue) -> None:
        while True:
            topic, ev = await q.get()
            site_key = topic.split(":", 1)[1]
            await ws.send_json({**ev, "site_key": site_key, **sites.get(site_key, {})})

    async with bus.subscribe(*topics) as q:
        sender = asyncio.create_task(pump(q))
        try:
            while True:                      # keep reading so a close is noticed
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()
