"""Report submission + evidence + status (Phase 2).

- POST /api/v1/reports                — submit a fraud report (202, non-blocking)
- POST /api/v1/reports/{id}/evidence  — attach validated evidence (quarantine)
- GET  /api/v1/reports/{id}           — status polling; evidence only when published

Submission requires consent and an authenticated reporter; accepts an
`Idempotency-Key` header so a retried POST cannot double-file (Doc 02 §9.4).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.idempotency import get_idempotent, store_idempotent
from app.core.security import hash_password
from app.db import get_db
from app.deps import get_current_user, get_jwt_service
from app.enums import EvidenceMediaType, ReportCategory, Role, UserStatus
from app.models import User
from app.resolver.banks import UnsupportedBankError
from app.resolver.emvco import EMVCoParseError
from app.resolver.normalize import NormalizationError
from app.services import report_service as svc
from app.services.image_guard import UploadValidationError, normalize_image
from app.storage import get_storage

router = APIRouter(prefix="/reports", tags=["reports"])

_PRIVILEGED = {Role.ANALYST, Role.SENIOR_ANALYST, Role.SUPERADMIN}


class AccountTarget(BaseModel):
    kind: Literal["ACCOUNT"] = "ACCOUNT"
    country: str | None = Field(default=None, min_length=2, max_length=2)
    bank: str = Field(min_length=1, max_length=50)
    account: str = Field(min_length=1, max_length=64)


class QRTarget(BaseModel):
    kind: Literal["QR"] = "QR"
    qr_payload: str = Field(min_length=1, max_length=512)


class ReportCreateRequest(BaseModel):
    target: AccountTarget | QRTarget = Field(discriminator="kind")
    category: ReportCategory
    severity: int = Field(ge=1, le=5)
    description: str = Field(min_length=20, max_length=5000)
    currency: str = Field(default="IDR", min_length=3, max_length=3)
    loss_amount: Decimal | None = Field(default=None, ge=0)
    incident_date: date | None = None
    consent: bool


class AnonymousReportRequest(ReportCreateRequest):
    """Public report submission: no account required, but reporter identity is
    captured. If the email already belongs to a registered user we attribute the
    report to that account (and keep its display name); otherwise we create a new
    USER account with the supplied name."""

    reporter_email: EmailStr
    reporter_name: str = Field(min_length=1, max_length=120)


async def _resolve_reporter(db: AsyncSession, email: str, name: str) -> tuple[User, bool]:
    """Return (user, created). Case-insensitive email match; race-safe create."""
    normalized = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized))
    if user is not None:
        return user, False
    user = User(
        email=normalized,
        display_name=name.strip() or None,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=Role.USER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        user = await db.scalar(select(User).where(User.email == normalized))
        if user is None:  # pragma: no cover - defensive
            raise
        return user, False
    await db.refresh(user)
    return user, True


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    body: ReportCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.consent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "consent is required to publish a report")

    redis = request.app.state.redis
    idem_scope = f"report:{user.id}"
    if idempotency_key:
        cached = await get_idempotent(redis, idem_scope, idempotency_key)
        if cached is not None:
            return cached

    try:
        if isinstance(body.target, AccountTarget):
            entity = await svc.resolve_bank_target(
                db,
                country=body.target.country,
                bank=body.target.bank,
                account=body.target.account,
            )
        else:
            entity = await svc.resolve_qr_target(db, qr_payload=body.target.qr_payload)
    except (UnsupportedBankError, NormalizationError, EMVCoParseError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        await svc.enforce_quotas(db, user_id=user.id, entity_id=entity.id)
    except svc.QuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc

    report = await svc.create_report(
        db,
        entity=entity,
        reporter_user_id=user.id,
        category=body.category.value,
        severity=body.severity,
        description=body.description,
        currency=body.currency,
        loss_amount=body.loss_amount,
        incident_date=body.incident_date,
    )
    payload = {
        "status": "accepted",
        "data": {
            "report_id": str(report.id),
            "processing_status": report.processing_status,
            "entity_masked": entity.account_masked,
        },
    }
    if idempotency_key:
        await store_idempotent(redis, idem_scope, idempotency_key, payload)
    return payload


@router.post("/anonymous", status_code=status.HTTP_202_ACCEPTED)
async def create_anonymous_report(
    body: AnonymousReportRequest,
    db: AsyncSession = Depends(get_db),
    jwt_service=Depends(get_jwt_service),
):
    """Public report submission (no login). Captures reporter name + email.

    - Existing email → attributed to that account; its display name is used
      (the supplied name is ignored) and no session is issued.
    - New email → a USER account is created with the supplied name and an access
      token is returned so the reporter can attach evidence and track the report.
    """
    if not body.consent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "consent is required to publish a report")

    try:
        if isinstance(body.target, AccountTarget):
            entity = await svc.resolve_bank_target(
                db,
                country=body.target.country,
                bank=body.target.bank,
                account=body.target.account,
            )
        else:
            entity = await svc.resolve_qr_target(db, qr_payload=body.target.qr_payload)
    except (UnsupportedBankError, NormalizationError, EMVCoParseError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    reporter, created = await _resolve_reporter(
        db, str(body.reporter_email), body.reporter_name
    )

    try:
        await svc.enforce_quotas(db, user_id=reporter.id, entity_id=entity.id)
    except svc.QuotaExceededError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc

    report = await svc.create_report(
        db,
        entity=entity,
        reporter_user_id=reporter.id,
        category=body.category.value,
        severity=body.severity,
        description=body.description,
        currency=body.currency,
        loss_amount=body.loss_amount,
        incident_date=body.incident_date,
    )

    data: dict = {
        "report_id": str(report.id),
        "processing_status": report.processing_status,
        "entity_masked": entity.account_masked,
        "reporter": {
            "email": reporter.email,
            "name": reporter.display_name or body.reporter_name.strip(),
            "is_new": created,
        },
    }
    if created:
        # New account → hand back a session so the reporter can upload evidence
        # and track the report. Existing accounts never get an implicit session.
        pair, _access_jti, _refresh_jti = jwt_service.issue_token_pair(
            user_id=str(reporter.id), role=reporter.role
        )
        data["access_token"] = pair.access_token
    return {"status": "accepted", "data": data}


@router.post("/{report_id}/evidence", status_code=status.HTTP_202_ACCEPTED)
async def upload_evidence(
    report_id: uuid.UUID,
    file: UploadFile = File(...),
    media_type: EvidenceMediaType = Form(default=EvidenceMediaType.TRANSFER_SLIP),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await svc.get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    if report.reporter_user_id != user.id and user.role not in _PRIVILEGED:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your report")
    if report.processing_status != "PROCESSING":
        raise HTTPException(status.HTTP_409_CONFLICT, "report is no longer accepting evidence")

    raw = await file.read()
    try:
        normalized = normalize_image(raw)
    except UploadValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    storage = get_storage()
    stored = storage.put_quarantine(data=normalized.data, content_type=normalized.content_type)
    evidence = await svc.add_evidence(
        db,
        report=report,
        quarantine_key=stored.key,
        media_type=media_type.value,
    )
    return {
        "status": "accepted",
        "data": {"evidence_id": str(evidence.id), "media_type": evidence.media_type},
    }


@router.get("/{report_id}")
async def get_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    report = await svc.get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    evidence = await svc.list_evidence(db, report_id)
    public_urls = {e.id: e.media_url for e in evidence}
    return {
        "status": "success",
        "data": svc.serialize_report(report, evidence, public_urls=public_urls),
    }
