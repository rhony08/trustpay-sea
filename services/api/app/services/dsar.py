"""DSAR: self-serve export + erasure of a user's own data (Phase 4B.7 / docs/10).

Erasure follows the data fate matrix: report **bodies are tombstoned** (kept
countable for scoring integrity), original quarantine evidence is purged (redacted
public copies kept), and the user's votes/flags/watchlist/notifications are
removed. `payment_entities` HMAC rows are **never deleted** (others' safety depends
on lookup) and the hash-chained `audit_logs` are immutable.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import append_audit
from app.models import (
    FraudReport,
    PaymentEntity,
    ReportEvidence,
    ReportVote,
    ReviewFlag,
    User,
    UserNotification,
    WatchlistEntry,
)
from app.storage import StorageError, get_storage


async def export_user_data(db: AsyncSession, user: User) -> dict:
    reports = list(
        await db.scalars(
            select(FraudReport).where(
                FraudReport.reporter_user_id == user.id,
                FraudReport.deleted_at.is_(None),
            )
        )
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
    storage = get_storage()
    now = datetime.now(UTC)

    reports = list(
        await db.scalars(select(FraudReport).where(FraudReport.reporter_user_id == user.id))
    )
    evidence_purged = 0
    reports_tombstoned = 0
    for report in reports:
        for item in await db.scalars(
            select(ReportEvidence).where(ReportEvidence.report_id == report.id)
        ):
            if item.original_quarantine_url:
                with contextlib.suppress(StorageError):
                    storage.delete(item.original_quarantine_url)
                item.original_quarantine_url = None
                evidence_purged += 1
        if report.deleted_at is None:
            report.description = None
            report.loss_amount = None
            report.deleted_at = now
            reports_tombstoned += 1

    votes = await db.execute(delete(ReportVote).where(ReportVote.voter_user_id == user.id))
    flags = await db.execute(delete(ReviewFlag).where(ReviewFlag.flagged_by_user_id == user.id))
    watches = await db.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user.id))
    notifications = await db.execute(
        delete(UserNotification).where(UserNotification.user_id == user.id)
    )
    await db.commit()

    await append_audit(
        db,
        action="dsar.erased",
        actor_user_id=user.id,
        subject_type="user",
        subject_id=user.id,
        note=f"reports_tombstoned={reports_tombstoned} evidence_purged={evidence_purged}",
    )
    return {
        "reports_tombstoned": reports_tombstoned,
        "evidence_purged": evidence_purged,
        "votes_deleted": votes.rowcount or 0,
        "flags_deleted": flags.rowcount or 0,
        "watchlist_deleted": watches.rowcount or 0,
        "notifications_deleted": notifications.rowcount or 0,
    }
