"""Report service (Phase 2.1 / 2.7 / 2.8).

Submission is non-blocking: create the report as `PROCESSING` and return; the
async worker (Phase 2.3) publishes it after fail-closed redaction. Quotas and a
duplicate-submission guard limit abuse (Doc 02 §5.2, §9).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import (
    AdminVerificationStatus,
    EntityType,
    ProcessingStatus,
    ReportStatus,
    Scheme,
)
from app.models import FraudReport, PaymentEntity, ReportEvidence
from app.resolver.banks import get_institution
from app.resolver.emvco import parse_emvco
from app.resolver.normalize import normalize_account, normalize_qr_identifier
from app.services.entity_service import upsert_entity


class ReportError(Exception):
    pass


class QuotaExceededError(ReportError):
    pass


async def resolve_bank_target(
    db: AsyncSession, *, country: str, bank: str, account: str
) -> PaymentEntity:
    settings = get_settings()
    institution = get_institution(country, bank)
    account_hash, masked = normalize_account(
        country=country,
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=institution,
        account_raw=account,
        kms_key=settings.account_hmac_key,
    )
    return await upsert_entity(
        db,
        entity_type=EntityType.BANK_ACCOUNT,
        scheme=Scheme.BANK,
        country_code=country,
        institution_code=institution.code,
        account_hash=account_hash,
        account_masked=masked,
    )


async def resolve_qr_target(db: AsyncSession, *, qr_payload: str) -> PaymentEntity:
    settings = get_settings()
    parsed = parse_emvco(qr_payload)
    country = parsed.country or "ID"
    account_hash, masked = normalize_qr_identifier(
        country=country,
        scheme=parsed.scheme,
        nmid=parsed.nmid or "",
        kms_key=settings.account_hmac_key,
    )
    return await upsert_entity(
        db,
        entity_type=EntityType.QR_CODE,
        scheme=parsed.scheme,
        country_code=country,
        institution_code=None,
        account_hash=account_hash,
        account_masked=masked,
        merchant_name=parsed.merchant_name,
        merchant_city=parsed.merchant_city,
        nmid=parsed.nmid,
        emvco_payload=qr_payload,
        mcc=parsed.mcc,
    )


async def _user_reports_since(db: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    return int(
        await db.scalar(
            select(func.count(FraudReport.id)).where(
                FraudReport.reporter_user_id == user_id,
                FraudReport.created_at >= since,
            )
        )
        or 0
    )


async def _entity_reports_since(db: AsyncSession, entity_id: uuid.UUID, since: datetime) -> int:
    return int(
        await db.scalar(
            select(func.count(FraudReport.id)).where(
                FraudReport.payment_entity_id == entity_id,
                FraudReport.created_at >= since,
            )
        )
        or 0
    )


async def enforce_quotas(db: AsyncSession, *, user_id: uuid.UUID, entity_id: uuid.UUID) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if await _user_reports_since(db, user_id, day_start) >= settings.report_daily_quota_per_user:
        raise QuotaExceededError("daily report quota reached")
    hour_ago = now - timedelta(hours=1)
    entity_hourly = await _entity_reports_since(db, entity_id, hour_ago)
    if entity_hourly >= settings.report_hourly_quota_per_entity:
        raise QuotaExceededError("hourly reports-per-entity quota reached")


async def create_report(
    db: AsyncSession,
    *,
    entity: PaymentEntity,
    reporter_user_id: uuid.UUID,
    category: str,
    severity: int,
    description: str,
    currency: str = "IDR",
    loss_amount: Decimal | None = None,
    incident_date: date | None = None,
) -> FraudReport:
    report = FraudReport(
        payment_entity_id=entity.id,
        reporter_user_id=reporter_user_id,
        category=category,
        severity=severity,
        currency=currency.upper(),
        loss_amount=loss_amount,
        incident_date=incident_date,
        description=description,
        processing_status=ProcessingStatus.PROCESSING,
        admin_verification_status=AdminVerificationStatus.PENDING,
        status=ReportStatus.ACTIVE,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def get_report(db: AsyncSession, report_id: uuid.UUID) -> FraudReport | None:
    return await db.get(FraudReport, report_id)


async def add_evidence(
    db: AsyncSession,
    *,
    report: FraudReport,
    quarantine_key: str,
    media_type: str,
) -> ReportEvidence:
    evidence = ReportEvidence(
        report_id=report.id,
        media_url="",  # stays empty until fail-closed redaction produces the public copy
        original_quarantine_url=quarantine_key,
        media_type=media_type,
        is_blurred_pii=True,
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)
    return evidence


async def list_evidence(db: AsyncSession, report_id: uuid.UUID) -> list[ReportEvidence]:
    rows = await db.scalars(
        select(ReportEvidence)
        .where(ReportEvidence.report_id == report_id)
        .order_by(ReportEvidence.created_at)
    )
    return list(rows)


async def list_published_reports(
    db: AsyncSession, entity_id: uuid.UUID, *, limit: int = 20
) -> list[FraudReport]:
    rows = await db.scalars(
        select(FraudReport)
        .where(
            FraudReport.payment_entity_id == entity_id,
            FraudReport.processing_status == ProcessingStatus.PUBLISHED,
            FraudReport.status == ReportStatus.ACTIVE,
        )
        .order_by(FraudReport.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def evidence_for_reports(
    db: AsyncSession, report_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ReportEvidence]]:
    if not report_ids:
        return {}
    rows = await db.scalars(select(ReportEvidence).where(ReportEvidence.report_id.in_(report_ids)))
    grouped: dict[uuid.UUID, list[ReportEvidence]] = {}
    for row in rows:
        grouped.setdefault(row.report_id, []).append(row)
    return grouped


def serialize_evidence(evidence: ReportEvidence, public_url: str, *, published: bool) -> dict:
    """Public evidence is only ever the redacted copy; never before publish."""
    return {
        "media_type": evidence.media_type,
        "media_url": public_url if published else None,
        "is_blurred_pii": evidence.is_blurred_pii,
        "ai_tampering_detected": evidence.ai_tampering_detected,
    }


def serialize_report(
    report: FraudReport,
    evidence: list[ReportEvidence] | None = None,
    *,
    public_urls: dict[uuid.UUID, str] | None = None,
) -> dict:
    published = report.processing_status == ProcessingStatus.PUBLISHED
    public_urls = public_urls or {}
    return {
        "id": str(report.id),
        "payment_entity_id": str(report.payment_entity_id),
        "category": report.category,
        "severity": report.severity,
        "currency": report.currency,
        "loss_amount": float(report.loss_amount) if report.loss_amount is not None else None,
        "incident_date": report.incident_date.isoformat() if report.incident_date else None,
        "description": report.description if published else None,
        "processing_status": report.processing_status,
        "admin_verification_status": report.admin_verification_status,
        "status": report.status,
        "ai_risk_score": report.ai_risk_score,
        "ai_tampering_detected": bool(
            report.ai_forensic_notes and report.ai_forensic_notes.get("tampering_detected")
        ),
        "evidence": [
            serialize_evidence(e, public_urls.get(e.id, ""), published=published)
            for e in (evidence or [])
        ]
        if published
        else [],
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
