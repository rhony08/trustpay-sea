"""Screen-API key management (Phase 9 / docs/09 §2).

Users self-serve DEMO keys; PARTNER/ENTERPRISE require an admin. Raw keys are
returned exactly once. Issue/rotate/revoke are written to the hash-chained audit.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.api_keys import WIB, daily_limit, generate_api_key
from app.core.audit import append_audit
from app.db import get_db
from app.deps import get_current_user
from app.enums import ApiKeyTier, Role
from app.models import ApiKey, User

router = APIRouter(prefix="/keys", tags=["keys"])

_PRIVILEGED = {Role.ANALYST, Role.SENIOR_ANALYST, Role.SUPERADMIN}
_SCOPES: dict[str, list[str]] = {
    ApiKeyTier.DEMO.value: ["screen:read"],
    ApiKeyTier.PARTNER.value: ["screen:read", "reports:write"],
    ApiKeyTier.ENTERPRISE.value: ["screen:read", "reports:write"],
}


class KeyRequest(BaseModel):
    name: str = Field(default="default", max_length=100)
    tier: ApiKeyTier = ApiKeyTier.DEMO


def _view(key: ApiKey) -> dict:
    return {
        "id": str(key.id),
        "name": key.name,
        "last4": key.last4,
        "tier": key.tier,
        "scopes": key.scopes,
        "is_active": key.is_active,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "rotated_at": key.rotated_at.isoformat() if key.rotated_at else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
    }


async def _owned_key(db: AsyncSession, key_id: uuid.UUID, user: User) -> ApiKey:
    key = await db.get(ApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "key not found")
    return key


@router.post("", status_code=status.HTTP_201_CREATED)
async def issue_key(
    body: KeyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.tier != ApiKeyTier.DEMO and user.role not in _PRIVILEGED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "partner keys require an analyst/admin")
    raw, key_hash, last4 = generate_api_key(get_settings().api_key_prefix)
    key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        last4=last4,
        tier=body.tier.value,
        scopes=_SCOPES[body.tier.value],
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    await append_audit(
        db,
        action="api_key.issued",
        actor_user_id=user.id,
        subject_type="api_key",
        subject_id=key.id,
        after={"tier": key.tier},
    )
    return {"status": "success", "data": {**_view(key), "api_key": raw}}


@router.get("")
async def list_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return {"status": "success", "data": {"keys": [_view(k) for k in rows]}}


@router.get("/usage")
async def key_usage(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    redis = request.app.state.redis
    rows = await db.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.is_active.is_(True))
    )
    today = datetime.now(WIB).strftime("%Y%m%d")
    usage = []
    for key in rows:
        used = int(await redis.get(f"screenq:key:{key.key_hash}:{today}") or 0)
        usage.append(
            {
                "id": str(key.id),
                "last4": key.last4,
                "tier": key.tier,
                "used_today": used,
                "daily_limit": daily_limit(key.tier),
            }
        )
    return {"status": "success", "data": {"usage": usage}}


@router.post("/{key_id}/rotate")
async def rotate_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = await _owned_key(db, key_id, user)
    raw, key_hash, last4 = generate_api_key(get_settings().api_key_prefix)
    key.key_hash = key_hash
    key.last4 = last4
    key.is_active = True
    key.rotated_at = datetime.now(WIB)
    await db.commit()
    await db.refresh(key)
    await append_audit(
        db,
        action="api_key.rotated",
        actor_user_id=user.id,
        subject_type="api_key",
        subject_id=key.id,
    )
    return {"status": "success", "data": {**_view(key), "api_key": raw}}


@router.delete("/{key_id}")
async def revoke_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = await _owned_key(db, key_id, user)
    key.is_active = False
    key.revoked_at = datetime.now(WIB)
    await db.commit()
    await append_audit(
        db,
        action="api_key.revoked",
        actor_user_id=user.id,
        subject_type="api_key",
        subject_id=key.id,
    )
    return {"status": "success", "data": _view(key)}
