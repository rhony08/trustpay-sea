"""DSAR: self-serve export + erasure of a user's own data (Phase 4B.7 / §9.8 H8).

Erasure deletes the user's reports (evidence cascades), their votes, flags and
watchlist rows. Entities are de-linked, not listed; audit history is immutable
and retained for integrity.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FraudReport,
    PaymentEntity,
    ReportVote,
    ReviewFlag,
    User,
    WatchlistEntry,
)


async def export_user_data(db: AsyncSession, user: User) -> dict:
    reports = list(
        await db.scalars(select(FraudReport).where(FraudReport.reporter_user_id == user.id))
    )
    entity_ids = [r.payment_entity_id for r in reports]
    entities: dict = {}
    if entity_ids:
        rows = await db.scalars(select(PaymentEntity).where(PaymentEntity.id.in_(entity_ids)))
        entities = {row.id: row for row in rows}

    return {
        "profile": {
            "email": user.email,
            "display_name": user.display_name,
            "reputation_score": user.reputation_score,
            "identity_trust": user.identity_trust,
            "phone_verified": user.phone_verified,
        },
        "reports": [
            {
                "id": str(r.id),
                "account_masked": entities[r.payment_entity_id].account_masked
                if r.payment_entity_id in entities
                else None,
                "category": r.category,
                "severity": r.severity,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ],
        "votes": [
            {"report_id": str(v.report_id), "vote": v.vote}
            for v in await db.scalars(select(ReportVote).where(ReportVote.voter_user_id == user.id))
        ],
        "flags": [
            {"id": str(f.id), "reason": f.reason, "status": f.status}
            for f in await db.scalars(
                select(ReviewFlag).where(ReviewFlag.flagged_by_user_id == user.id)
            )
        ],
    }


async def erase_user_data(db: AsyncSession, user: User) -> dict:
    # Votes/flags by the user on any report.
    votes = await db.execute(delete(ReportVote).where(ReportVote.voter_user_id == user.id))
    flags = await db.execute(delete(ReviewFlag).where(ReviewFlag.flagged_by_user_id == user.id))
    watches = await db.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user.id))
    # The user's own reports (evidence cascades); their votes/flags cascade too.
    reports = await db.execute(delete(FraudReport).where(FraudReport.reporter_user_id == user.id))
    await db.commit()
    return {
        "reports_deleted": reports.rowcount or 0,
        "votes_deleted": votes.rowcount or 0,
        "flags_deleted": flags.rowcount or 0,
        "watchlist_deleted": watches.rowcount or 0,
    }
