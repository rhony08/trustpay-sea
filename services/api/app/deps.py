"""FastAPI dependencies: DB session, current user (JWT cookie or bearer), RBAC,
CSRF (ADR-020), and MFA step-up guards."""

import time
import uuid
from collections.abc import Callable

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.security import JWTService, TokenError
from app.core.token_family import TokenFamilyStore
from app.db import get_db
from app.enums import Role, UserStatus
from app.models import User

_bearer = HTTPBearer(auto_error=False)

ACCESS_COOKIE = "tp_access"
REFRESH_COOKIE = "tp_refresh"

_role_rank: dict[str, int] = {
    Role.USER: 0,
    Role.ANALYST: 1,
    Role.SENIOR_ANALYST: 2,
    Role.SUPERADMIN: 3,
}

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_jwt_service(settings: Settings = Depends(get_settings)) -> JWTService:
    return JWTService(settings)


def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


def get_token_family_store(redis: aioredis.Redis = Depends(get_redis)) -> TokenFamilyStore:
    return TokenFamilyStore(redis)


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """Bearer header wins (non-browser clients); else HttpOnly access cookie."""
    if credentials is not None:
        return credentials.credentials
    return request.cookies.get(ACCESS_COOKIE)


async def get_auth_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    jwt_service: JWTService = Depends(get_jwt_service),
    family_store: TokenFamilyStore = Depends(get_token_family_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    token = _extract_token(request, credentials)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing credentials")
    # CSRF (ADR-020): only cookie-authenticated mutating requests are ambient
    # (bearer/ API-key clients are not driven by the browser). Enforced here —
    # the exact point where auth is known to come from the cookie — so
    # anonymous mutating endpoints are unaffected.
    if (
        credentials is None
        and request.method in _MUTATING_METHODS
        and not request.url.path.startswith("/api/v1/auth")
    ):
        cookie_value = request.cookies.get(settings.csrf_cookie, "")
        header_value = request.headers.get(settings.csrf_header, "")
        if not cookie_value or not header_value or cookie_value != header_value:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    try:
        payload = jwt_service.decode(token, expected_type="access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if await family_store.is_access_denied(payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token revoked")
    return payload


async def get_current_user(
    payload: dict = Depends(get_auth_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    if user.status == UserStatus.BANNED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account banned")
    return user


def require_role(minimum: Role) -> Callable[..., User]:
    """RBAC dependency factory: ANALYST+ or SENIOR_ANALYST+ etc."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if _role_rank[user.role] < _role_rank[minimum]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"requires role {minimum} or higher",
            )
        return user

    return _guard


def require_recent_mfa(
    payload: dict = Depends(get_auth_payload),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Step-up guard (ADR-020): sensitive admin mutations need a fresh WebAuthn
    assertion. Enforced only when MFA is required for admins (prod)."""
    if not settings.mfa_required_for_admins:
        return payload
    mfa_at = payload.get("mfa_at")
    if not isinstance(mfa_at, int):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "recent WebAuthn MFA required for this action"
        )
    if time.time() - mfa_at > settings.mfa_step_up_seconds:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"MFA step-up expired ({settings.mfa_step_up_seconds}s) — re-authenticate",
        )
    return payload
