"""Auth schemas + routes: signup / login / refresh (rotation) / logout / me."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenError, hash_password, verify_password
from app.db import get_db
from app.deps import (
    get_current_user,
    get_jwt_service,
    get_token_family_store,
)
from app.enums import Role, UserStatus
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    role: str
    status: str
    identity_trust: int
    reputation_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=Role.USER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _issue_tokens(user, jwt_service, family_store)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
):
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or user.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if user.status == UserStatus.BANNED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account banned")
    return await _issue_tokens(user, jwt_service, family_store)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
):
    try:
        payload = jwt_service.decode(body.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    family = payload.get("fam")
    jti = payload["jti"]
    if not family:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token missing family")
    if await family_store.is_revoked(family):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session revoked")
    if await family_store.is_used(family, jti):
        # reuse detected → revoke the whole login session (rotation guard, §9.2)
        await family_store.revoke(family)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "refresh token reuse detected; session revoked"
        )

    await family_store.register(family, jti)  # burn this jti (rotation)
    pair, _access_jti, new_refresh_jti = jwt_service.issue_token_pair(
        user_id=payload["sub"], role=payload["role"], family=family
    )
    await family_store.register(family, new_refresh_jti)
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
):
    try:
        payload = jwt_service.decode(body.refresh_token, expected_type="refresh")
    except TokenError:
        return  # already invalid — nothing to revoke
    family = payload.get("fam")
    if family:
        await family_store.revoke(family)
    return None


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


async def _issue_tokens(user: User, jwt_service, family_store) -> TokenResponse:
    # Fresh tokens are NOT pre-marked used — a jti is burned only when it is
    # presented for rotation (that's what makes re-presentation = reuse).
    pair, _access_jti, _refresh_jti = jwt_service.issue_token_pair(
        user_id=str(user.id), role=user.role
    )
    return pair
