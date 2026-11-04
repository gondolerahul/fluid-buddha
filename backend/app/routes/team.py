"""
The account's team and audit log (M2-1). Roles are enforced centrally
(``app.auth.roles``): anyone can see the team, Admins manage it, only an Owner
can grant or take away Owner.

    GET    /tenant/team                          members + pending invitations
    POST   /tenant/team/invitations              {email, role} → emailed link
    DELETE /tenant/team/invitations/{id}
    PATCH  /tenant/team/members/{user_id}        {role}
    DELETE /tenant/team/members/{user_id}
    GET    /tenant/audit                         ?before=&action=&actor=&limit=
    GET    /tenant/audit.csv                     the same, as CSV
"""
from __future__ import annotations

import csv
import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import roles, team
from app.auth.security import current_member
from app.config import get_settings
from app.db import get_session
from app.notify import email as mailer
from app.notify import templates

router = APIRouter(prefix="/tenant", tags=["team"])


@router.get("/team")
async def get_team(m: team.Member = Depends(current_member),
                   db: AsyncSession = Depends(get_session)) -> dict:
    return {"members": await team.members(db, m.tenant.id),
            "invitations": await team.pending_invitations(db, m.tenant.id),
            "me": {"id": str(m.user_id), "role": m.role}}


class InviteIn(BaseModel):
    email: EmailStr
    role: str


def _invite_email(m: team.Member, to: str, role: str, link: str) -> mailer.Email:
    account = m.tenant.name or m.tenant.email
    who = m.name or m.email
    text = (f"{who} invited you to join {account} on FluidBuddha as {role}.\n\n"
            f"Accept the invitation: {link}\n\nThe link works once and expires in "
            f"{team.INVITE_DAYS} days. If you weren't expecting this, ignore this email.")
    html = templates.layout(
        f"Join {account} on FluidBuddha",
        templates.paragraph(f"{who} invited you to join {account} as {role}.")
        + templates.button("Accept the invitation", link)
        + templates.paragraph(f"The link works once and expires in {team.INVITE_DAYS} days."),
        footer="If you weren't expecting this, you can ignore this email.")
    return mailer.Email(to=to, subject=f"{who} invited you to {account} on FluidBuddha",
                        text=text, html=html, kind="invitation", tenant_id=m.tenant.id)


@router.post("/team/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(body: InviteIn, m: team.Member = Depends(current_member),
                            db: AsyncSession = Depends(get_session)) -> dict:
    if body.role not in roles.ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown role")
    if not roles.can_assign(m.role, body.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Owner can invite an Owner.")
    existing = await team.user_by_email(db, body.email)
    if existing and await team.role_of(db, m.tenant.id, existing["id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "They're already in this account.")
    iid, token = await team.invite(db, m.tenant.id, body.email, body.role, m.user_id)
    link = f"{get_settings().console_url.rstrip('/')}/invite?token={token}"
    emailed = True
    try:
        await mailer.enqueue(db, _invite_email(m, body.email, body.role, link))
    except mailer.EmailNotConfigured:
        emailed = False   # the Admin copies the link from the response instead
    await db.commit()
    # The link is returned so the Admin can share it another way too.
    return {"id": str(iid), "email": body.email.lower(), "role": body.role, "link": link,
            "emailed": emailed}


@router.delete("/team/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invitation(invitation_id: uuid.UUID, m: team.Member = Depends(current_member),
                            db: AsyncSession = Depends(get_session)) -> None:
    if not await team.revoke_invitation(db, m.tenant.id, invitation_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    await db.commit()


class RoleIn(BaseModel):
    role: str


async def _target_role(db: AsyncSession, m: team.Member, user_id: uuid.UUID) -> str:
    role = await team.role_of(db, m.tenant.id, user_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return role


async def _keep_an_owner(db: AsyncSession, m: team.Member, current: str) -> None:
    if current == "owner" and await team.owner_count(db, m.tenant.id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An account needs at least one Owner. Make someone else Owner first.")


@router.patch("/team/members/{user_id}")
async def change_role(user_id: uuid.UUID, body: RoleIn,
                      m: team.Member = Depends(current_member),
                      db: AsyncSession = Depends(get_session)) -> dict:
    if body.role not in roles.ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown role")
    current = await _target_role(db, m, user_id)
    if not (roles.can_assign(m.role, current) and roles.can_assign(m.role, body.role)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Owner can change an Owner.")
    if body.role != "owner":
        await _keep_an_owner(db, m, current)
    await team.set_role(db, m.tenant.id, user_id, body.role)
    await db.commit()
    return {"id": str(user_id), "role": body.role, "previous": current}


@router.delete("/team/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(user_id: uuid.UUID, m: team.Member = Depends(current_member),
                        db: AsyncSession = Depends(get_session)) -> None:
    current = await _target_role(db, m, user_id)
    if not roles.can_assign(m.role, current):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an Owner can remove an Owner.")
    await _keep_an_owner(db, m, current)
    await team.remove_member(db, m.tenant.id, user_id)
    await db.commit()


# ---- audit log -----------------------------------------------------------------

@router.get("/audit")
async def get_audit(
    before: Optional[int] = Query(None, ge=1), action: Optional[str] = Query(None, max_length=80),
    actor: Optional[str] = Query(None, max_length=200), limit: int = Query(100, ge=1, le=500),
    m: team.Member = Depends(current_member), db: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await audit.search(db, m.tenant.id, limit=limit, before=before, action=action,
                              actor=actor)


@router.get("/audit.csv")
async def get_audit_csv(
    action: Optional[str] = Query(None, max_length=80),
    actor: Optional[str] = Query(None, max_length=200),
    m: team.Member = Depends(current_member), db: AsyncSession = Depends(get_session),
) -> Response:
    rows = await audit.search(db, m.tenant.id, limit=10_000, action=action, actor=actor)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "who", "action", "target_type", "target_id", "ip", "request_id"])
    for r in rows:
        # A leading =,+,-,@ would run as a formula in a spreadsheet.
        safe = [("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v
                for v in (r["at"], r["actor_email"], r["action"], r["target_type"],
                          r["target_id"], r["ip"], r["request_id"])]
        w.writerow(safe)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'})
