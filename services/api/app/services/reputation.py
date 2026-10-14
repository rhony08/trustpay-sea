"""Reputation, trust tiers and community badges (Phase 3B.1–3B.3)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import BadgeType, EntityVerificationStatus, TrustTier
from app.models import FraudReport, PaymentEntity, User, UserBadge


def tier_for(user: User) -> TrustTier:
    return TrustTier.from_reputation(user.reputation_score)


async def grant_badge(
    db: AsyncSession, user_id: uuid.UUID, badge: BadgeType, scope: str = ""
) -> UserBadge:
    existing = await db.scalar(
        select(UserBadge).where(
            UserBadge.user_id == user_id,
            UserBadge.badge == badge.value,
            UserBadge.scope == scope,
        )
    )
    if existing is not None:
        return existing
    entry = UserBadge(user_id=user_id, badge=badge.value, scope=scope)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_badges(db: AsyncSession, user_id: uuid.UUID) -> list[UserBadge]:
    rows = await db.scalars(
        select(UserBadge).where(UserBadge.user_id == user_id).order_by(UserBadge.granted_at)
    )
    return list(rows)


async def grant_pioneer_badges(db: AsyncSession, entity_id: uuid.UUID) -> int:
    """Grant PIONEER_WARN to the first reporter of an entity that got verified."""
    reporter_id = await db.scalar(
        select(FraudReport.reporter_user_id)
        .where(
            FraudReport.payment_entity_id == entity_id,
            FraudReport.reporter_user_id.is_not(None),
        )
        .order_by(FraudReport.created_at)
        .limit(1)
    )
    if reporter_id is None:
        return 0
    await grant_badge(db, reporter_id, BadgeType.PIONEER_WARN, scope=str(entity_id))
    return 1


async def set_entity_verification(
    db: AsyncSession, entity: PaymentEntity, status: EntityVerificationStatus
) -> None:
    """Admin/gov verification flip — the trigger for Pioneer Warn badges."""
    entity.verification_status = status
    if status in (
        EntityVerificationStatus.ADMIN_CONFIRMED_FRAUD,
        EntityVerificationStatus.GOV_BLACKLISTED,
    ):
        await grant_pioneer_badges(db, entity.id)
    await db.commit()


async def apply_verified_reporter(db: AsyncSession, user: User, phone: str | None = None) -> None:
    """Phone-verified reporter: raises identity trust (+30) + reputation, grants badge."""
    if phone:
        user.phone = phone
    user.phone_verified = True
    user.identity_trust = min(100, user.identity_trust + 30)
    user.reputation_score = min(100, user.reputation_score + 10)
    await db.commit()
    await grant_badge(db, user.id, BadgeType.VERIFIED_REPORTER)
