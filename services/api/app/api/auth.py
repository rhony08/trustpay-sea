"""Auth schemas + routes: signup / login (MFA step for admins) / refresh /
logout / me / WebAuthn enrollment + assertion (ADR-020).

Browser clients get HttpOnly cookies (tp_access / tp_refresh) + a readable CSRF
cookie; non-browser clients keep receiving bearer tokens in the JSON body.
Rotation, family revocation and reuse detection from Phase 0 are unchanged.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers import (
    parse_authentication_credential_json,
    parse_registration_credential_json,
)

from app.config import Settings, get_settings
from app.core import webauthn_service as wa
from app.core.security import TokenError, hash_password, verify_password
from app.core.webauthn_service import WebAuthnError
from app.db import get_db
from app.deps import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    get_current_user,
    get_jwt_service,
    get_redis,
    get_token_family_store,
)
from app.enums import Role, UserStatus
from app.models import User, WebAuthnCredential

router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_ROLES = {Role.ANALYST, Role.SENIOR_ANALYST, Role.SUPERADMIN}


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None  # None → read from tp_refresh cookie


class TokenResponse(BaseModel):
    access_token: str | None = None  # body tokens are for non-browser clients
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    mfa_required: bool = False


class MfaChallengeResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


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


class WebAuthnOptionsResponse(BaseModel):
    options: dict
    challenge: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    challenge: str
    credential: dict  # WebAuthn RegistrationCredentialJSON, parsed by the lib


class WebAuthnAuthVerifyRequest(BaseModel):
    mfa_token: str
    challenge: str
    credential: dict  # WebAuthn AuthenticationCredentialJSON


def _set_session_cookies(response: Response, settings: Settings, access: str, refresh: str) -> None:
    secure = settings.cookie_secure
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_ttl_seconds,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.refresh_token_ttl_seconds,
    )
    # readable by JS on purpose — must be echoed in X-CSRF-Token (double submit)
    response.set_cookie(
        settings.csrf_cookie,
        wa_token_placeholder(),  # replaced below; keeps ordering obvious
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_ttl_seconds,
    )


def wa_token_placeholder() -> str:
    import secrets

    return secrets.token_urlsafe(32)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    settings: Settings = Depends(get_settings),
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
    return await _finish_login(response, settings, jwt_service, user)


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    settings: Settings = Depends(get_settings),
):
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or user.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if user.status == UserStatus.BANNED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account banned")

    if user.role in ADMIN_ROLES:
        has_credential = await db.scalar(
            select(WebAuthnCredential.id).where(WebAuthnCredential.user_id == user.id).limit(1)
        )
        if settings.mfa_required_for_admins and not has_credential:
            # prod: no passkey → no admin login (ADR-020); enrollment is done by
            # another authenticated admin or via the bootstrap seed
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "admin account has no passkey enrolled — ask another admin to enroll one",
            )
        if has_credential or settings.mfa_required_for_admins:
            # MFA step: password alone never yields a session for admin roles
            return MfaChallengeResponse(
                mfa_token=jwt_service.issue_mfa_token(user_id=str(user.id), role=user.role)
            )

    return await _finish_login(response, settings, jwt_service, user)


@router.post("/mfa/webauthn/options", response_model=WebAuthnOptionsResponse)
async def mfa_webauthn_options(
    body: dict,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    settings: Settings = Depends(get_settings),
    redis=Depends(get_redis),
):
    mfa_token = body.get("mfa_token", "")
    try:
        payload = jwt_service.decode(mfa_token, expected_type="mfa")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    credentials = await db.scalars(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == uuid.UUID(payload["sub"]))
    )
    creds = list(credentials)
    if not creds:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no passkey enrolled")
    return await wa.authentication_options(
        redis, settings=settings, user_id=payload["sub"], credentials=creds
    )


@router.post("/mfa/webauthn/verify", response_model=TokenResponse)
async def mfa_webauthn_verify(
    body: WebAuthnAuthVerifyRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
    settings: Settings = Depends(get_settings),
    redis=Depends(get_redis),
):
    try:
        payload = jwt_service.decode(body.mfa_token, expected_type="mfa")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    credential = await db.scalar(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
    )
    if credential is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no passkey enrolled")
    try:
        new_count = await wa.verify_authentication(
            redis,
            settings=settings,
            user_id=payload["sub"],
            credential=parse_authentication_credential_json(body.credential),
            expected_challenge=body.challenge,
            stored_credential=credential,
        )
    except WebAuthnError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    credential.sign_count = new_count
    await db.commit()
    return await _finish_login(response, settings, jwt_service, user, mfa_at=wa.now())


@router.post("/webauthn/register/options", response_model=WebAuthnOptionsResponse)
async def webauthn_register_options(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    redis=Depends(get_redis),
):
    """Any authenticated user may enroll a passkey; admins NEED one in prod."""
    return await wa.registration_options(
        redis, settings=settings, user_id=str(user.id), email=user.email
    )


@router.post("/webauthn/register/verify", status_code=status.HTTP_201_CREATED)
async def webauthn_register_verify(
    body: WebAuthnRegisterVerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis=Depends(get_redis),
):
    try:
        result = await wa.verify_registration(
            redis,
            settings=settings,
            user_id=str(user.id),
            credential=parse_registration_credential_json(body.credential),
            expected_challenge=body.challenge,
        )
    except WebAuthnError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    existing = await db.scalar(
        select(WebAuthnCredential).where(
            WebAuthnCredential.credential_id == result["credential_id"]
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "passkey already enrolled")
    credential = WebAuthnCredential(
        user_id=user.id,
        credential_id=result["credential_id"],
        public_key=result["public_key"],
        sign_count=result["sign_count"],
        transports=result["transports"] or None,
    )
    db.add(credential)
    await db.commit()
    return {"status": "success", "data": {"credential_id": result["credential_id"]}}


@router.get("/webauthn/credentials")
async def list_webauthn_credentials(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id))
    return {
        "status": "success",
        "data": {
            "credentials": [
                {
                    "credential_id": c.credential_id,
                    "label": c.label,
                    "transports": c.transports,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in rows
            ]
        },
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
    settings: Settings = Depends(get_settings),
):
    token = body.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing refresh token")
    try:
        payload = jwt_service.decode(token, expected_type="refresh")
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
    _set_session_cookies(response, settings, pair.access_token, pair.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        mfa_required=False,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    request: Request,
    response: Response,
    jwt_service=Depends(get_jwt_service),
    family_store=Depends(get_token_family_store),
    settings: Settings = Depends(get_settings),
):
    token = body.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if token:
        try:
            payload = jwt_service.decode(token, expected_type="refresh")
        except TokenError:
            payload = None
        if payload and payload.get("fam"):
            await family_store.revoke(payload["fam"])
    for cookie in (ACCESS_COOKIE, REFRESH_COOKIE, settings.csrf_cookie):
        response.delete_cookie(cookie, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    return None


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


async def _finish_login(
    response: Response,
    settings: Settings,
    jwt_service,
    user: User,
    mfa_at: int | None = None,
) -> TokenResponse:
    pair, _access_jti, _refresh_jti = jwt_service.issue_token_pair(
        user_id=str(user.id), role=user.role, mfa_at=mfa_at
    )
    _set_session_cookies(response, settings, pair.access_token, pair.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        mfa_required=False,
    )
