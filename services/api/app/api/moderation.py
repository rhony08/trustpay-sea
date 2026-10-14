"""Community moderation API (Phase 4): votes, review flags, admin resolution."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, require_role
from app.enums import ReviewFlagReason, ReviewFlagStatus, Role
from app.models import ReviewFlag, User
from app.services import moderation_service as svc
from app.services.report_service import get_report

router = APIRouter(tags=["moderation"])


class VoteRequest(BaseModel):
    vote: int = Field(ge=-1, le=1)


class FlagRequest(BaseModel):
    reason: ReviewFlagReason
    details: str | None = Field(default=None, max_length=1000)


class ResolveRequest(BaseModel):
    decision: ReviewFlagStatus
    notes: str | None = Field(default=None, max_length=1000)


def _flag_view(flag: ReviewFlag) -> dict:
    return {
        "id": str(flag.id),
        "report_id": str(flag.report_id),
        "reason": flag.reason,
        "details": flag.details,
        "status": flag.status,
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
    }


@router.post("/reports/{report_id}/vote")
async def vote(
    report_id: uuid.UUID,
    body: VoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    up, down = await svc.cast_vote(db, report_id=report_id, user_id=user.id, vote=body.vote)
    return {"status": "success", "data": {"upvotes": up, "downvotes": down}}


@router.delete("/reports/{report_id}/vote", status_code=status.HTTP_200_OK)
async def unvote(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    up, down = await svc.remove_vote(db, report_id=report_id, user_id=user.id)
    return {"status": "success", "data": {"upvotes": up, "downvotes": down}}


@router.post("/reports/{report_id}/flags", status_code=status.HTTP_201_CREATED)
async def flag_report(
    report_id: uuid.UUID,
    body: FlagRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")

    settings = get_settings()
    redis = request.app.state.redis
    bucket = f"flagrate:{user.id}:{int(time.time() // 3600)}"
    count = await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, 3600)
    if count > settings.flag_rate_per_hour:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "flag rate limit exceeded")

    try:
        flag = await svc.create_flag(
            db, report=report, user_id=user.id, reason=body.reason.value, details=body.details
        )
    except svc.FlagConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"status": "success", "data": _flag_view(flag)}


@router.get("/flags/me")
async def my_flags(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    flags = await svc.list_my_flags(db, user.id)
    return {"status": "success", "data": {"flags": [_flag_view(f) for f in flags]}}


@router.get("/admin/flags")
async def admin_flag_queue(
    status_filter: ReviewFlagStatus | None = ReviewFlagStatus.PENDING,
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    flags = await svc.list_flag_queue(db, status=status_filter)
    return {"status": "success", "data": {"flags": [_flag_view(f) for f in flags]}}


@router.post("/admin/flags/{flag_id}/resolve")
async def admin_resolve_flag(
    flag_id: uuid.UUID,
    body: ResolveRequest,
    admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    flag = await db.get(ReviewFlag, flag_id)
    if flag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "flag not found")
    try:
        resolved = await svc.resolve_flag(
            db, flag=flag, admin=admin, decision=body.decision.value, notes=body.notes
        )
    except svc.ModerationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "success", "data": _flag_view(resolved)}
