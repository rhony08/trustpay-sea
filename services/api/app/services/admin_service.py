"""Admin portal: dashboard, audit viewer, and four-eyes dual-control (Phase 6.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import append_audit, verify_chain
from app.enums import (
    AdminVerificationStatus,
    DisputeStatus,
    ProcessingStatus,
    ReviewFlagStatus,
    UserStatus,
)
from app.models import (
    AdminApproval,
    AuditLog,
    FraudReport,
    OwnerDispute,
    PaymentEntity,
    ReviewFlag,
    User,
)


class AdminError(Exception):
    pass


async def dashboard_counts(db: AsyncSession) -> dict:
    async def _count(model, *filters) -> int:
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        return int(await db.scalar(stmt) or 0)

    return {
        "pending_reports": await _count(
            FraudReport, FraudReport.admin_verification_status == AdminVerificationStatus.PENDING
        ),
        "processing_reports": await _count(
            FraudReport, FraudReport.processing_status == ProcessingStatus.PROCESSING
        ),
        "pending_flags": await _count(ReviewFlag, ReviewFlag.status == ReviewFlagStatus.PENDING),
        "open_disputes": await _count(
            OwnerDispute, OwnerDispute.status == DisputeStatus.UNDER_REVIEW
        ),
        "pending_approvals": await _count(AdminApproval, AdminApproval.status == "PENDING"),
    }


async def audit_view(db: AsyncSession, *, limit: int = 50) -> dict:
    rows = list(await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))
    return {
        "chain_ok": await verify_chain(db),
        "entries": [
            {
                "id": row.id,
                "action": row.action,
                "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                "subject_type": row.subject_type,
                "subject_id": str(row.subject_id) if row.subject_id else None,
                "note": row.note,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


async def request_approval(
    db: AsyncSession,
    *,
    admin: User,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID,
    payload: dict | None = None,
) -> AdminApproval:
    if action not in _EXECUTORS:
        raise AdminError(f"unknown approval action: {action}")
    approval = AdminApproval(
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload or {},
        requested_by=admin.id,
        status="PENDING",
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def approve(db: AsyncSession, *, approval: AdminApproval, admin: User) -> AdminApproval:
    if approval.status != "PENDING":
        raise AdminError("approval is not pending")
    if approval.requested_by == admin.id:
        raise AdminError("a second, different admin must approve (four-eyes)")
    approval.status = "APPROVED"
    approval.approved_by = admin.id
    approval.approved_at = datetime.now(UTC)
    await db.commit()
    await _EXECUTORS[approval.action](db, approval)
    await append_audit(
        db,
        action=f"admin.approval.{approval.action}",
        actor_user_id=admin.id,
        subject_type=approval.subject_type,
        subject_id=approval.subject_id,
        after={"approval_id": str(approval.id)},
    )
    await db.refresh(approval)
    return approval


async def _execute_gov_override(db: AsyncSession, approval: AdminApproval) -> None:
    entity = await db.get(PaymentEntity, approval.subject_id)
    if entity is None:
        raise AdminError("entity not found")
    entity.is_gov_blacklisted = True
    entity.gov_source = (approval.payload or {}).get("source", "mock-gov-feed")
    await db.commit()
    from app.services.risk_scorer import recompute_entity_score

    await recompute_entity_score(db, entity)


async def _execute_ban_user(db: AsyncSession, approval: AdminApproval) -> None:
    user = await db.get(User, approval.subject_id)
    if user is None:
        raise AdminError("user not found")
    user.status = UserStatus.BANNED
    await db.commit()


_EXECUTORS = {
    "gov_override": _execute_gov_override,
    "ban_user": _execute_ban_user,
}


async def sync_gov_feed(db: AsyncSession) -> int:
    """Apply the mock gov feed to matching entities (score 100 + attribution)."""
    from app.services import gov_adapter
    from app.services.risk_scorer import recompute_entity_score

    applied = 0
    for entity in await db.scalars(select(PaymentEntity)):
        source = gov_adapter.lookup(entity.account_hash)
        if source and not entity.is_gov_blacklisted:
            entity.is_gov_blacklisted = True
            entity.gov_source = source
            await db.commit()
            await recompute_entity_score(db, entity)
            applied += 1
    return applied
