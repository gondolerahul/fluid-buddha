"""
The install's licence (M3-5), for self-hosted installs.

    GET /tenant/licence   its state (any signed-in member: the console's banner)
    PUT /tenant/licence   install a new one {key} (Owner)

On the hosted service ``self_hosted`` is false and nothing is enforced.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import team
from app.auth.security import current_member
from app.db import get_session
from app.licence import core, guard

router = APIRouter(prefix="/tenant", tags=["licence"])

REASONS = {
    "malformed": "That isn't a FluidBuddha licence key.",
    "unknown_key": "That licence was signed with a key this version doesn't know. Upgrade, or ask for a new licence.",
    "bad_signature": "That licence key has been changed or is incomplete: paste it again exactly as issued.",
}


async def _usage(db: AsyncSession) -> dict:
    sites = (await db.execute(text("SELECT count(*) FROM tenant_websites"))).scalar() or 0
    seats = (await db.execute(text(
        "SELECT (SELECT count(DISTINCT user_id) FROM memberships) + (SELECT count(*) FROM invitations "
        "WHERE accepted_at IS NULL AND expires_at > now())"))).scalar() or 0
    return {"sites": int(sites), "seats": int(seats)}


@router.get("/licence")
async def get_licence(m: team.Member = Depends(current_member), db: AsyncSession = Depends(get_session)) -> dict:
    if not guard.enabled():
        return {"self_hosted": False}
    st = await guard.current()
    return {"self_hosted": True, **st, "usage": await _usage(db)}


class LicenceIn(BaseModel):
    key: str = Field(..., min_length=10, max_length=8000)


@router.put("/licence")
async def install_licence(body: LicenceIn, m: team.Member = Depends(current_member),
                          db: AsyncSession = Depends(get_session)) -> dict:
    if not guard.enabled():
        raise HTTPException(status.HTTP_409_CONFLICT, "Licences are only for self-hosted installs.")
    token = "".join(body.key.split())
    try:
        lic = core.parse(token)
    except core.LicenceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, REASONS[exc.reason])
    if not core.state(lic)["usable"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "That licence has expired (and its grace period is over). Ask for a renewal.")
    await db.execute(text(
        "INSERT INTO install_licence (id, token, installed_by) VALUES (1, :t, :u) "
        "ON CONFLICT (id) DO UPDATE SET token = EXCLUDED.token, installed_at = now(), "
        "installed_by = EXCLUDED.installed_by"), {"t": token, "u": m.user_id})
    await db.commit()
    await guard.refresh(db)
    return {"self_hosted": True, **(await guard.current()), "usage": await _usage(db)}
