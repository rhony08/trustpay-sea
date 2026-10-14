"""Community profile: trust tier, badges, phone verification, watchlist, quiz (Phase 3B)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.otp import confirm_otp, start_otp
from app.db import get_db
from app.deps import get_current_user
from app.enums import BadgeType, RiskLevel
from app.models import PaymentEntity, User
from app.services import reputation, scam_quiz, watchlist_service

router = APIRouter(prefix="/profile", tags=["profile"])


class PhoneStart(BaseModel):
    phone: str = Field(min_length=6, max_length=30)


class PhoneConfirm(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class WatchRequest(BaseModel):
    entity_id: uuid.UUID


class QuizSubmit(BaseModel):
    answers: list[int]


def _badge_view(badges) -> list[dict]:
    return [
        {"badge": b.badge, "scope": b.scope, "granted_at": b.granted_at.isoformat()} for b in badges
    ]


@router.get("/me")
async def profile_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    badges = await reputation.list_badges(db, user.id)
    return {
        "status": "success",
        "data": {
            "email": user.email,
            "display_name": user.display_name,
            "reputation_score": user.reputation_score,
            "identity_trust": user.identity_trust,
            "tier": reputation.tier_for(user).value,
            "phone_verified": user.phone_verified,
            "badges": _badge_view(badges),
        },
    }


@router.post("/verify/phone/start")
async def verify_phone_start(
    body: PhoneStart,
    request: Request,
    user: User = Depends(get_current_user),
):
    settings = get_settings()
    code = await start_otp(request.app.state.redis, str(user.id))
    # Production sends via SMS provider. Dev returns the code for the demo flow.
    payload: dict = {"sent": True, "phone": body.phone}
    if settings.environment != "prod":
        payload["dev_code"] = code
    return {"status": "success", "data": payload}


@router.post("/verify/phone/confirm")
async def verify_phone_confirm(
    body: PhoneConfirm,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await confirm_otp(request.app.state.redis, str(user.id), body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired code")
    await reputation.apply_verified_reporter(db, user)
    badges = await reputation.list_badges(db, user.id)
    return {
        "status": "success",
        "data": {
            "phone_verified": True,
            "identity_trust": user.identity_trust,
            "reputation_score": user.reputation_score,
            "tier": reputation.tier_for(user).value,
            "badges": _badge_view(badges),
        },
    }


@router.get("/badges")
async def my_badges(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    badges = await reputation.list_badges(db, user.id)
    return {"status": "success", "data": {"badges": _badge_view(badges)}}


@router.get("/watchlist")
async def get_watchlist(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    entries = await watchlist_service.list_watch(db, user.id)
    entity_ids = [e.payment_entity_id for e in entries]
    entities: dict[uuid.UUID, PaymentEntity] = {}
    if entity_ids:
        rows = await db.scalars(select(PaymentEntity).where(PaymentEntity.id.in_(entity_ids)))
        entities = {row.id: row for row in rows}
    data = []
    for entry in entries:
        entity = entities.get(entry.payment_entity_id)
        if entity is None:
            continue
        data.append(
            {
                "entity_id": str(entity.id),
                "entity_type": entity.entity_type,
                "country": entity.country_code,
                "institution": entity.institution_code,
                "account_masked": entity.account_masked,
                "risk_score": entity.risk_score,
                "risk_level": RiskLevel.from_score(entity.risk_score).value,
            }
        )
    return {"status": "success", "data": {"watchlist": data}}


@router.post("/watchlist", status_code=status.HTTP_201_CREATED)
async def add_watchlist(
    body: WatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await db.get(PaymentEntity, body.entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")
    entry = await watchlist_service.add_watch(db, user.id, entity.id)
    return {
        "status": "success",
        "data": {"entity_id": str(entity.id), "watched": True, "id": str(entry.id)},
    }


@router.delete("/watchlist/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    entity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await watchlist_service.remove_watch(db, user.id, entity_id)
    return None


@router.post("/quiz/submit")
async def submit_quiz(
    body: QuizSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    correct, passed = scam_quiz.grade(body.answers)
    if passed:
        await reputation.grant_badge(db, user.id, BadgeType.ANTI_SCAM_AWARE)
    return {"status": "success", "data": {"correct": correct, "passed": passed}}
