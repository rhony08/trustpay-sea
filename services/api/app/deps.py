"""FastAPI dependencies: DB session, current user (JWT), RBAC role guards."""

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

_role_rank: dict[str, int] = {
    Role.USER: 0,
    Role.ANALYST: 1,
    Role.SENIOR_ANALYST: 2,
    Role.SUPERADMIN: 3,
}


def get_jwt_service(settings: Settings = Depends(get_settings)) -> JWTService:
    return JWTService(settings)


def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


def get_token_family_store(redis: aioredis.Redis = Depends(get_redis)) -> TokenFamilyStore:
    return TokenFamilyStore(redis)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    jwt_service: JWTService = Depends(get_jwt_service),
    family_store: TokenFamilyStore = Depends(get_token_family_store),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = jwt_service.decode(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if await family_store.is_access_denied(payload["jti"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token revoked")
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
