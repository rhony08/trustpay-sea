"""Admin portal API (Phase 6.5): dashboard, audit viewer, four-eyes approvals."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_role
from app.enums import Role
from app.models import AdminApproval, User
from app.services import admin_service as svc

router = APIRouter(prefix="/admin", tags=["admin"])


class ApprovalRequest(BaseModel):
    action: str = Field(pattern="^(gov_override|ban_user)$")
    subject_type: str = Field(min_length=1, max_length=30)
    subject_id: uuid.UUID
    payload: dict | None = None


class SemakMuleCheckRequest(BaseModel):
    bank: str = Field(min_length=1, max_length=50)
    account: str = Field(min_length=1, max_length=64)


def _approval_view(a: AdminApproval) -> dict:
    return {
        "id": str(a.id),
        "action": a.action,
        "subject_type": a.subject_type,
        "subject_id": str(a.subject_id),
        "status": a.status,
        "requested_by": str(a.requested_by),
        "approved_by": str(a.approved_by) if a.approved_by else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/dashboard")
async def dashboard(
    _admin: User = Depends(require_role(Role.ANALYST)), db: AsyncSession = Depends(get_db)
):
    return {"status": "success", "data": await svc.dashboard_counts(db)}


@router.get("/audit")
async def audit(
    limit: int = 50,
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    return {"status": "success", "data": await svc.audit_view(db, limit=min(limit, 200))}


@router.get("/reports/{report_id}")
async def admin_report(
    report_id: uuid.UUID,
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    detail = await svc.report_detail(db, report_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return {"status": "success", "data": detail}


@router.get("/approvals")
async def list_approvals(
    status_filter: str | None = "PENDING",
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AdminApproval).order_by(AdminApproval.created_at)
    if status_filter:
        stmt = stmt.where(AdminApproval.status == status_filter)
    rows = await db.scalars(stmt)
    return {"status": "success", "data": {"approvals": [_approval_view(a) for a in rows]}}


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
async def create_approval(
    body: ApprovalRequest,
    admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    try:
        approval = await svc.request_approval(
            db,
            admin=admin,
            action=body.action,
            subject_type=body.subject_type,
            subject_id=body.subject_id,
            payload=body.payload,
        )
    except svc.AdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "success", "data": _approval_view(approval)}


@router.post("/approvals/{approval_id}/approve")
async def approve(
    approval_id: uuid.UUID,
    admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    approval = await db.get(AdminApproval, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "approval not found")
    try:
        resolved = await svc.approve(db, approval=approval, admin=admin)
    except svc.AdminError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return {"status": "success", "data": _approval_view(resolved)}


@router.post("/gov/sync")
async def gov_sync(
    _admin: User = Depends(require_role(Role.SUPERADMIN)), db: AsyncSession = Depends(get_db)
):
    return {"status": "success", "data": {"applied": await svc.sync_gov_feed(db)}}


@router.post("/gov/semakmule/check")
async def semakmule_check(
    body: SemakMuleCheckRequest,
    _admin: User = Depends(require_role(Role.ANALYST)),
    db: AsyncSession = Depends(get_db),
):
    """Run a PDRM Semak Mule check (MY) and persist the flag to a matching entity."""
    from app.config import get_settings
    from app.enums import EntityType, Scheme
    from app.resolver.banks import get_institution
    from app.resolver.normalize import normalize_account
    from app.services.entity_service import get_entity_by_hash
    from app.services.semakmule import get_semakmule_client, infer_category

    client = get_semakmule_client()
    if not client.enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Semak Mule is not configured (SEMAKMULE_API_KEY)"
        )

    entity = None
    bank_type = None
    try:
        institution = get_institution("MY", body.bank)
        bank_type = institution.bank_type
        account_hash, _ = normalize_account(
            country="MY",
            scheme=Scheme.BANK,
            entity_type=EntityType.BANK_ACCOUNT,
            institution=institution,
            account_raw=body.account,
            kms_key=get_settings().account_hmac_key,
        )
        entity = await get_entity_by_hash(db, account_hash)
    except Exception:  # noqa: BLE001 — unsupported bank/decode just means nothing to persist
        entity = None

    category = infer_category(bank_type=bank_type, value=body.account)
    result = await client.check(category=category, value=body.account)

    persisted = False
    if entity is not None and result.available and result.found and not entity.is_gov_blacklisted:
        from app.services.risk_scorer import recompute_entity_score

        entity.is_gov_blacklisted = True
        entity.gov_source = result.source
        await db.commit()
        await recompute_entity_score(db, entity)
        persisted = True

    return {
        "status": "success",
        "data": {**result.to_dict(), "category": category, "persisted": persisted},
    }
