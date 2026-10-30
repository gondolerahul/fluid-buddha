"""
Tenant auth routes (req A): self-service register + login with email/password,
returning a JWT bearer token, plus ``/auth/me`` for the current tenant.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    create_access_token,
    current_tenant,
    hash_password,
    verify_password,
)
from app.db import get_session
from app.tenancy import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=256)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant: dict


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_session)):
    existing = await store.get_tenant_by_email(db, body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    tenant = await store.create_tenant(
        db, email=body.email, password_hash=hash_password(body.password), name=body.name
    )
    token = create_access_token(tenant.id)
    logger.info("tenant registered: %s", tenant.email)
    return TokenResponse(access_token=token, tenant=tenant.public())


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_session)):
    row = await store.get_tenant_by_email(db, body.email)
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(row["id"])
    tenant = store.Tenant(
        id=row["id"], email=row["email"], name=row["name"], created_at=row["created_at"]
    )
    return TokenResponse(access_token=token, tenant=tenant.public())


@router.get("/me")
async def me(tenant: store.Tenant = Depends(current_tenant)) -> dict:
    return tenant.public()
