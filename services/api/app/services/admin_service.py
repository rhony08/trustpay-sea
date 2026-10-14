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
    ReportEvidence,
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


# --- Enriched queues for the admin portal UI -------------------------------


async def _entity_index(db: AsyncSession, entity_ids: set) -> dict:
    if not entity_ids:
        return {}
    rows = await db.scalars(select(PaymentEntity).where(PaymentEntity.id.in_(entity_ids)))
    return {row.id: row for row in rows}


def _entity_brief(entity: PaymentEntity | None) -> dict | None:
    if entity is None:
        return None
    return {
        "id": str(entity.id),
        "entity_type": entity.entity_type,
        "country": entity.country_code,
        "institution": entity.institution_code,
        "account_masked": entity.account_masked,
        "risk_score": entity.risk_score,
        "is_gov_blacklisted": entity.is_gov_blacklisted,
    }


def _report_brief(report: FraudReport | None) -> dict | None:
    if report is None:
        return None
    return {
        "id": str(report.id),
        "category": report.category,
        "severity": report.severity,
        "description": report.description,
        "status": report.status,
        "admin_verification_status": report.admin_verification_status,
        "upvotes": report.upvotes_count,
        "downvotes": report.downvotes_count,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


async def flag_queue(
    db: AsyncSession, *, status: str | None = ReviewFlagStatus.PENDING
) -> list[dict]:
    stmt = select(ReviewFlag).order_by(ReviewFlag.created_at)
    if status:
        stmt = stmt.where(ReviewFlag.status == status)
    flags = list(await db.scalars(stmt))
    report_ids = {f.report_id for f in flags}
    reports = (
        {
            r.id: r
            for r in await db.scalars(select(FraudReport).where(FraudReport.id.in_(report_ids)))
        }
        if report_ids
        else {}
    )
    entities = await _entity_index(db, {r.payment_entity_id for r in reports.values()})

    out = []
    for flag in flags:
        report = reports.get(flag.report_id)
        entity = entities.get(report.payment_entity_id) if report else None
        out.append(
            {
                "id": str(flag.id),
                "reason": flag.reason,
                "details": flag.details,
                "status": flag.status,
                "created_at": flag.created_at.isoformat() if flag.created_at else None,
                "report": _report_brief(report),
                "entity": _entity_brief(entity),
            }
        )
    return out


async def dispute_queue(
    db: AsyncSession, *, status: str | None = DisputeStatus.UNDER_REVIEW
) -> list[dict]:
    stmt = select(OwnerDispute).order_by(OwnerDispute.created_at)
    if status:
        stmt = stmt.where(OwnerDispute.status == status)
    disputes = list(await db.scalars(stmt))
    entities = await _entity_index(db, {d.payment_entity_id for d in disputes})

    out = []
    for dispute in disputes:
        out.append(
            {
                "id": str(dispute.id),
                "claim_stage": dispute.claim_stage,
                "status": dispute.status,
                "proof_type": dispute.owner_proof_type,
                "dispute_reason": dispute.dispute_reason,
                "justification": dispute.justification_statement,
                "counter_evidence_urls": dispute.counter_evidence_urls,
                "target_report_id": str(dispute.target_report_id)
                if dispute.target_report_id
                else None,
                "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
                "entity": _entity_brief(entities.get(dispute.payment_entity_id)),
            }
        )
    return out


async def report_detail(db: AsyncSession, report_id) -> dict | None:
    report = await db.get(FraudReport, report_id)
    if report is None:
        return None
    entity = await db.get(PaymentEntity, report.payment_entity_id)
    evidence = list(
        await db.scalars(select(ReportEvidence).where(ReportEvidence.report_id == report_id))
    )
    return {
        **_report_brief(report),
        "currency": report.currency,
        "loss_amount": float(report.loss_amount) if report.loss_amount is not None else None,
        "ai_risk_score": report.ai_risk_score,
        "ai_forensic_notes": report.ai_forensic_notes,
        "is_legal_hold": report.is_legal_hold,
        "entity": _entity_brief(entity),
        "evidence": [
            {
                "media_type": e.media_type,
                "media_url": e.media_url,
                "is_blurred_pii": e.is_blurred_pii,
                "ai_tampering_detected": e.ai_tampering_detected,
            }
            for e in evidence
        ],
    }
