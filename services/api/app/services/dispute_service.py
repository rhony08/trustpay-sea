"""Owner claim, dispute & safe-harbor freeze (Phase 5).

Two-step flow (ADR-004): the owner first proves control (T1 passbook/mbanking,
T1b merchant NMID, T2 micro-deposit OTP), then submits a reason + justification
for each report they dispute. Admin adjudicates — removal is never automatic.

Safe-harbor is **rise-only**: it can cap a score from rising while disputed, but
must never pull an already high/verified score down (anti-gaming, Doc 02 §5.1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import append_audit
from app.core.otp import confirm_otp
from app.enums import (
    DisputeStatus,
    HolderNameSource,
    OwnerProofType,
    ReportStatus,
    UserStatus,
)
from app.models import FraudReport, OwnerDispute, PaymentEntity, User

SAFE_HARBOR_CAP = 45


class DisputeError(Exception):
    pass


def verify_ownership_proof(
    entity: PaymentEntity, proof_type: str, declared_reference: str | None
) -> bool:
    """Mock-first doc verification (real OCR/KYC in Phase 7).

    Merchant-NMID tier is deterministic: the declared NMID must match the entity.
    Document tiers (passbook/mbanking) are accepted in the demo.
    """
    if proof_type == OwnerProofType.MERCHANT_PORTAL_NMID:
        if not entity.nmid or not declared_reference:
            return False
        return declared_reference.strip() == entity.nmid
    return proof_type in (
        OwnerProofType.BANK_PASSBOOK,
        OwnerProofType.MBANKING_SCREENSHOT,
    )


async def _active_claim(
    db: AsyncSession, entity_id: uuid.UUID, user_id: uuid.UUID
) -> OwnerDispute | None:
    return await db.scalar(
        select(OwnerDispute).where(
            OwnerDispute.payment_entity_id == entity_id,
            OwnerDispute.claimed_by_user_id == user_id,
        )
    )


async def submit_claim(
    db: AsyncSession,
    *,
    entity: PaymentEntity,
    user: User,
    proof_type: str,
    proof_document_url: str,
    declared_reference: str | None = None,
) -> OwnerDispute:
    if entity.owner_claimed_by is not None and entity.owner_claimed_by != user.id:
        raise DisputeError("entity is already claimed by another owner")

    dispute = await _active_claim(db, entity.id, user.id)
    if dispute is None:
        dispute = OwnerDispute(
            payment_entity_id=entity.id,
            claimed_by_user_id=user.id,
            claim_stage=DisputeStatus.SUBMITTED,
            owner_proof_type=proof_type,
            owner_proof_document_url=proof_document_url,
            status=DisputeStatus.SUBMITTED,
        )
        db.add(dispute)
    else:
        dispute.owner_proof_type = proof_type
        dispute.owner_proof_document_url = proof_document_url

    if proof_type == OwnerProofType.MICRO_DEPOSIT_OTP:
        # Awaiting the micro-deposit OTP confirmation (T2).
        await db.commit()
        await db.refresh(dispute)
        return dispute

    await _promote_or_reject(db, dispute, entity, user, declared_reference)
    await db.refresh(dispute)
    return dispute


async def verify_micro_deposit(
    db: AsyncSession, *, entity: PaymentEntity, user: User, code: str, redis: Redis
) -> OwnerDispute:
    dispute = await _active_claim(db, entity.id, user.id)
    if dispute is None:
        raise DisputeError("no pending claim for micro-deposit verification")
    if await confirm_otp(redis, str(entity.id), code, scope="deposit"):
        await _set_under_review(db, dispute, entity, user)
    else:
        dispute.claim_stage = DisputeStatus.REJECTED_IDENTITY
        dispute.status = DisputeStatus.REJECTED_IDENTITY
        await db.commit()
    await db.refresh(dispute)
    return dispute


async def _promote_or_reject(
    db: AsyncSession,
    dispute: OwnerDispute,
    entity: PaymentEntity,
    user: User,
    declared_reference: str | None,
) -> None:
    if verify_ownership_proof(entity, dispute.owner_proof_type, declared_reference):
        await _set_under_review(db, dispute, entity, user)
    else:
        dispute.claim_stage = DisputeStatus.REJECTED_IDENTITY
        dispute.status = DisputeStatus.REJECTED_IDENTITY
        await append_audit(
            db,
            action="claim.rejected_identity",
            actor_user_id=user.id,
            subject_type="payment_entity",
            subject_id=entity.id,
        )


async def _set_under_review(
    db: AsyncSession, dispute: OwnerDispute, entity: PaymentEntity, user: User
) -> None:
    dispute.claim_stage = DisputeStatus.UNDER_REVIEW
    dispute.status = DisputeStatus.UNDER_REVIEW
    entity.owner_claimed_by = user.id
    entity.is_owner_verified = True
    entity.is_under_dispute = True
    entity.dispute_hold_score_cap = SAFE_HARBOR_CAP
    if entity.holder_name:
        entity.holder_name_source = HolderNameSource.OWNER_KYC_PROOF
    await db.commit()
    await append_audit(
        db,
        action="claim.under_review",
        actor_user_id=user.id,
        subject_type="payment_entity",
        subject_id=entity.id,
        note="ownership proven; safe-harbor engaged (rise-only)",
    )


async def submit_dispute(
    db: AsyncSession,
    *,
    entity: PaymentEntity,
    user: User,
    reason: str,
    justification: str,
    counter_evidence_urls: list[str] | None = None,
    target_report_id: uuid.UUID | None = None,
) -> OwnerDispute:
    dispute = await _active_claim(db, entity.id, user.id)
    if dispute is None or entity.owner_claimed_by != user.id:
        raise DisputeError("you must prove ownership before disputing")
    dispute.dispute_reason = reason
    dispute.justification_statement = justification
    dispute.counter_evidence_urls = counter_evidence_urls or []
    dispute.target_report_id = target_report_id
    await db.commit()
    await db.refresh(dispute)
    return dispute


async def resolve_dispute(
    db: AsyncSession,
    *,
    dispute: OwnerDispute,
    entity: PaymentEntity,
    admin: User,
    decision: str,
    notes: str | None = None,
) -> OwnerDispute:
    if decision not in (
        DisputeStatus.APPROVED_REMOVED,
        DisputeStatus.REJECTED_UPHELD,
        DisputeStatus.SETTLEMENT,
    ):
        raise DisputeError("decision must be APPROVED_REMOVED, REJECTED_UPHELD or SETTLEMENT")

    dispute.status = decision
    dispute.claim_stage = decision
    dispute.reviewed_by_admin_id = admin.id
    dispute.resolution_notes = notes
    dispute.resolved_at = datetime.now(UTC)
    # Any adjudication ends the safe-harbor freeze (reviews handled per decision).
    entity.is_under_dispute = False

    if decision == DisputeStatus.APPROVED_REMOVED:
        await _act_on_reports(
            db, entity, dispute.target_report_id, ReportStatus.REMOVED_BY_DISPUTE, penalize=True
        )
    elif decision == DisputeStatus.SETTLEMENT:
        await _act_on_reports(
            db,
            entity,
            dispute.target_report_id,
            ReportStatus.RESOLVED_BY_SETTLEMENT,
            penalize=False,
        )
    await db.commit()

    await append_audit(
        db,
        action=f"dispute.{decision.lower()}",
        actor_user_id=admin.id,
        subject_type="owner_dispute",
        subject_id=dispute.id,
        after={"decision": decision, "entity_id": str(entity.id)},
        note=notes,
    )
    from app.services.risk_scorer import recompute_entity_score

    await recompute_entity_score(db, entity)
    await db.refresh(dispute)
    return dispute


async def _act_on_reports(
    db: AsyncSession,
    entity: PaymentEntity,
    target_report_id: uuid.UUID | None,
    new_status: ReportStatus,
    *,
    penalize: bool,
) -> None:
    stmt = select(FraudReport).where(FraudReport.payment_entity_id == entity.id)
    if target_report_id is not None:
        stmt = stmt.where(FraudReport.id == target_report_id)
    for report in await db.scalars(stmt):
        report.status = new_status
        if penalize and report.reporter_user_id:
            reporter = await db.get(User, report.reporter_user_id)
            if reporter is not None and reporter.status == UserStatus.ACTIVE:
                reporter.status = UserStatus.WARNED


def apply_dispute_cap(entity: PaymentEntity, proposed_score: int) -> int:
    """Rise-only safe-harbor: cap new rises, never reduce an existing score."""
    if not entity.is_under_dispute:
        return proposed_score
    return max(entity.risk_score, min(proposed_score, entity.dispute_hold_score_cap))


async def pin_owner_response(
    db: AsyncSession, *, entity: PaymentEntity, user: User, response: str
) -> PaymentEntity:
    if entity.owner_claimed_by != user.id or not entity.is_owner_verified:
        raise DisputeError("only the verified owner may post a response")
    entity.owner_response = response
    await db.commit()
    await db.refresh(entity)
    return entity


__all__ = [
    "DisputeError",
    "apply_dispute_cap",
    "pin_owner_response",
    "resolve_dispute",
    "submit_claim",
    "submit_dispute",
    "verify_micro_deposit",
    "verify_ownership_proof",
]
