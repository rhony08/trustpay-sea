"""Owner claim, dispute & admin adjudication API (Phase 5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.otp import start_otp
from app.db import get_db
from app.deps import get_current_user, require_role
from app.enums import DisputeReason, DisputeStatus, OwnerProofType, Role
from app.models import OwnerDispute, PaymentEntity, User
from app.services import dispute_service as svc

router = APIRouter(tags=["disputes"])


class ClaimRequest(BaseModel):
    proof_type: OwnerProofType
    proof_document_url: str = Field(min_length=1, max_length=1024)
    declared_reference: str | None = Field(default=None, max_length=100)


class MicroDepositVerify(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class DisputeRequest(BaseModel):
    reason: DisputeReason
    justification: str = Field(min_length=10, max_length=4000)
    counter_evidence_urls: list[str] | None = None
    target_report_id: uuid.UUID | None = None


class ResolveRequest(BaseModel):
    decision: DisputeStatus
    notes: str | None = Field(default=None, max_length=2000)


class OwnerResponseRequest(BaseModel):
    response: str = Field(min_length=1, max_length=2000)


def _view(dispute: OwnerDispute) -> dict:
    return {
        "id": str(dispute.id),
        "entity_id": str(dispute.payment_entity_id),
        "claim_stage": dispute.claim_stage,
        "status": dispute.status,
        "proof_type": dispute.owner_proof_type,
        "dispute_reason": dispute.dispute_reason,
        "justification": dispute.justification_statement,
        "counter_evidence_urls": dispute.counter_evidence_urls,
        "resolution_notes": dispute.resolution_notes,
        "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        "resolved_at": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
    }


async def _get_entity(db: AsyncSession, entity_id: uuid.UUID) -> PaymentEntity:
    entity = await db.get(PaymentEntity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")
    return entity


@router.post("/entities/{entity_id}/claim", status_code=status.HTTP_202_ACCEPTED)
async def submit_claim(
    entity_id: uuid.UUID,
    body: ClaimRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await _get_entity(db, entity_id)
    try:
        dispute = await svc.submit_claim(
            db,
            entity=entity,
            user=user,
            proof_type=body.proof_type.value,
            proof_document_url=body.proof_document_url,
            declared_reference=body.declared_reference,
        )
    except svc.DisputeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {
        "status": "accepted",
        "data": {**_view(dispute), "note": "We never ask for your OTP by link or email."},
    }


@router.post("/entities/{entity_id}/claim/micro-deposit/start")
async def micro_deposit_start(
    entity_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_entity(db, entity_id)
    code = await start_otp(request.app.state.redis, str(entity_id), scope="deposit")
    payload: dict = {
        "note": "We sent a small deposit with a reference. Enter the reference code it contains.",
        "sent": True,
    }
    if get_settings().environment != "prod":
        payload["dev_code"] = code
    return {"status": "success", "data": payload}


@router.post("/entities/{entity_id}/claim/micro-deposit/verify")
async def micro_deposit_verify(
    entity_id: uuid.UUID,
    body: MicroDepositVerify,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await _get_entity(db, entity_id)
    try:
        dispute = await svc.verify_micro_deposit(
            db, entity=entity, user=user, code=body.code, redis=request.app.state.redis
        )
    except svc.DisputeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "success", "data": _view(dispute)}


@router.post("/entities/{entity_id}/disputes", status_code=status.HTTP_201_CREATED)
async def submit_dispute(
    entity_id: uuid.UUID,
    body: DisputeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await _get_entity(db, entity_id)
    try:
        dispute = await svc.submit_dispute(
            db,
            entity=entity,
            user=user,
            reason=body.reason.value,
            justification=body.justification,
            counter_evidence_urls=body.counter_evidence_urls,
            target_report_id=body.target_report_id,
        )
    except svc.DisputeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return {"status": "success", "data": _view(dispute)}


@router.patch("/entities/{entity_id}/owner-response")
async def owner_response(
    entity_id: uuid.UUID,
    body: OwnerResponseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await _get_entity(db, entity_id)
    try:
        await svc.pin_owner_response(db, entity=entity, user=user, response=body.response)
    except svc.DisputeError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return {"status": "success", "data": {"owner_response": entity.owner_response}}


@router.get("/disputes/me")
async def my_disputes(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(select(OwnerDispute).where(OwnerDispute.claimed_by_user_id == user.id))
    return {"status": "success", "data": {"disputes": [_view(d) for d in rows]}}


@router.get("/admin/disputes")
async def admin_queue(
    status_filter: DisputeStatus | None = DisputeStatus.UNDER_REVIEW,
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    from app.services import admin_service

    disputes = await admin_service.dispute_queue(
        db, status=status_filter.value if status_filter else None
    )
    return {"status": "success", "data": {"disputes": disputes}}


@router.post("/admin/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: uuid.UUID,
    body: ResolveRequest,
    admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    dispute = await db.get(OwnerDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dispute not found")
    entity = await _get_entity(db, dispute.payment_entity_id)
    try:
        resolved = await svc.resolve_dispute(
            db,
            dispute=dispute,
            entity=entity,
            admin=admin,
            decision=body.decision.value,
            notes=body.notes,
        )
    except svc.DisputeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "success", "data": _view(resolved)}
