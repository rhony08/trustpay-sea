"""Community moderation: votes, flags, admin resolution (Phase 4).

Anti-abuse invariants:
- one vote per user per report (DB PK) — no double voting;
- one flag per user per report per reason (DB unique) + a Redis rate cap;
- admin resolution is the ONLY way a flag hides a report (never auto-hide);
- every trust-altering action is written to the hash-chained audit log.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import append_audit
from app.enums import ReportStatus, ReviewFlagStatus, UserStatus
from app.models import FraudReport, PaymentEntity, ReportVote, ReviewFlag, User

# A flagger with this ratio of dismissed flags (min sample) is abusing flags.
BAD_FAITH_MIN_SAMPLE = 5
BAD_FAITH_DISMISSED_RATIO = 0.9


class ModerationError(Exception):
    pass


class FlagConflictError(ModerationError):
    pass


async def recompute_votes(db: AsyncSession, report_id: uuid.UUID) -> tuple[int, int]:
    up = int(
        await db.scalar(
            select(func.count())
            .select_from(ReportVote)
            .where(ReportVote.report_id == report_id, ReportVote.vote == 1)
        )
        or 0
    )
    down = int(
        await db.scalar(
            select(func.count())
            .select_from(ReportVote)
            .where(ReportVote.report_id == report_id, ReportVote.vote == -1)
        )
        or 0
    )
    report = await db.get(FraudReport, report_id)
    if report is not None:
        report.upvotes_count = up
        report.downvotes_count = down
        await db.commit()
    return up, down


async def cast_vote(
    db: AsyncSession, *, report_id: uuid.UUID, user_id: uuid.UUID, vote: int
) -> tuple[int, int]:
    if vote not in (-1, 1):
        raise ModerationError("vote must be +1 or -1")
    existing = await db.get(ReportVote, (report_id, user_id))
    if existing is None:
        db.add(ReportVote(report_id=report_id, voter_user_id=user_id, vote=vote))
    else:
        existing.vote = vote
    await db.commit()
    return await recompute_votes(db, report_id)


async def remove_vote(
    db: AsyncSession, *, report_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[int, int]:
    existing = await db.get(ReportVote, (report_id, user_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    return await recompute_votes(db, report_id)


async def create_flag(
    db: AsyncSession,
    *,
    report: FraudReport,
    user_id: uuid.UUID,
    reason: str,
    details: str | None = None,
) -> ReviewFlag:
    existing = await db.scalar(
        select(ReviewFlag).where(
            ReviewFlag.report_id == report.id,
            ReviewFlag.flagged_by_user_id == user_id,
            ReviewFlag.reason == reason,
        )
    )
    if existing is not None:
        raise FlagConflictError("you already flagged this report for that reason")
    flag = ReviewFlag(
        report_id=report.id,
        flagged_by_user_id=user_id,
        reason=reason,
        details=details,
        status=ReviewFlagStatus.PENDING,
    )
    db.add(flag)
    report.flags_count = (report.flags_count or 0) + 1
    await db.commit()
    await db.refresh(flag)
    return flag


async def list_my_flags(db: AsyncSession, user_id: uuid.UUID) -> list[ReviewFlag]:
    rows = await db.scalars(
        select(ReviewFlag)
        .where(ReviewFlag.flagged_by_user_id == user_id)
        .order_by(ReviewFlag.created_at.desc())
    )
    return list(rows)


async def list_flag_queue(
    db: AsyncSession, *, status: str | None = ReviewFlagStatus.PENDING
) -> list[ReviewFlag]:
    stmt = select(ReviewFlag).order_by(ReviewFlag.created_at)
    if status:
        stmt = stmt.where(ReviewFlag.status == status)
    return list(await db.scalars(stmt))


async def _check_bad_faith(db: AsyncSession, flagger_id: uuid.UUID | None) -> bool:
    if flagger_id is None:
        return False
    total = int(
        await db.scalar(
            select(func.count(ReviewFlag.id)).where(ReviewFlag.flagged_by_user_id == flagger_id)
        )
        or 0
    )
    if total < BAD_FAITH_MIN_SAMPLE:
        return False
    dismissed = int(
        await db.scalar(
            select(func.count(ReviewFlag.id)).where(
                ReviewFlag.flagged_by_user_id == flagger_id,
                ReviewFlag.status == ReviewFlagStatus.DISMISSED,
            )
        )
        or 0
    )
    if dismissed / total < BAD_FAITH_DISMISSED_RATIO:
        return False
    user = await db.get(User, flagger_id)
    if user is not None and user.status == UserStatus.ACTIVE:
        user.status = UserStatus.WARNED
        await append_audit(
            db,
            action="user.warned_bad_faith_flagger",
            subject_type="user",
            subject_id=user.id,
            note=f"dismissed {dismissed}/{total} flags",
        )
    return True


async def resolve_flag(
    db: AsyncSession,
    *,
    flag: ReviewFlag,
    admin: User,
    decision: str,
    notes: str | None = None,
) -> ReviewFlag:
    if decision not in (ReviewFlagStatus.UPHELD, ReviewFlagStatus.DISMISSED):
        raise ModerationError("decision must be UPHELD or DISMISSED")
    flag.status = decision
    flag.reviewed_by_admin_id = admin.id

    report = await db.get(FraudReport, flag.report_id)
    if decision == ReviewFlagStatus.UPHELD and report is not None:
        # Enforcement: upheld flag hides the report (excluded from score + feed).
        report.status = ReportStatus.HIDDEN
        reporter = await db.get(User, report.reporter_user_id) if report.reporter_user_id else None
        if reporter is not None and reporter.status == UserStatus.ACTIVE:
            reporter.status = UserStatus.WARNED
    await db.commit()

    await append_audit(
        db,
        action=f"flag.{decision.lower()}",
        actor_user_id=admin.id,
        subject_type="review_flag",
        subject_id=flag.id,
        after={"decision": decision, "report_id": str(flag.report_id)},
        note=notes,
    )
    await _check_bad_faith(db, flag.flagged_by_user_id)
    if report is not None:
        from app.services.risk_scorer import recompute_entity_score

        entity = await db.get(PaymentEntity, report.payment_entity_id)
        if entity is not None:
            await recompute_entity_score(db, entity)
    await db.refresh(flag)
    return flag
