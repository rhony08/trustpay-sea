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
from app.resolver.normalize import normalize_account, normalize_phone, normalize_qr_identifier
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
    phone_hash = None
    if (institution.bank_type or "").upper() == "E_WALLET":
        phone_hash, _ = normalize_phone(
            country=country, phone=account, kms_key=settings.account_hmac_key
        )
    entity = await upsert_entity(
        db,
        entity_type=EntityType.BANK_ACCOUNT,
        scheme=Scheme.BANK,
        country_code=country,
        institution_code=institution.code,
        account_hash=account_hash,
        account_masked=masked,
        phone_hash=phone_hash,
    )
    await _apply_government_signal(
        db, entity, country=country, account=account, bank_type=institution.bank_type
    )
    return entity


async def _apply_government_signal(
    db: AsyncSession,
    entity: PaymentEntity,
    *,
    country: str,
    account: str,
    bank_type: str | None = None,
) -> None:
    """Best-effort gov check at report time (authenticated path): flag + rescore.

    Only Malaysia (PDRM Semak Mule) for now; e-wallets use the *telefon* checker.
    Failures are ignored — a gov outage must never block report submission.
    """
    if country.upper() != "MY":
        return
    from app.services.risk_scorer import recompute_entity_score
    from app.services.semakmule import get_semakmule_client, infer_category

    client = get_semakmule_client()
    if not client.enabled:
        return
    category = infer_category(bank_type=bank_type, value=account)
    try:
        result = await client.check(category=category, value=account)
    except Exception:  # noqa: BLE001 — never block the report
        return
    if result.available and result.found and not entity.is_gov_blacklisted:
        entity.is_gov_blacklisted = True
        entity.gov_source = result.source
        await db.commit()
        await recompute_entity_score(db, entity)


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
            FraudReport.deleted_at.is_(None),
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


def serialize_forensics(notes: dict | None) -> dict | None:
    """Public-safe subset of `ai_forensic_notes` (Doc 12 asymmetric redaction).

    Never exposes reporter-side OCR (sender/balance/raw text) — only the
    destination-side fields needed to verify the recipient, plus already-masked
    NER hints.
    """
    if not notes:
        return None
    ocr = notes.get("ocr") if isinstance(notes.get("ocr"), dict) else {}
    ocr_public = (
        {
            "recipient": ocr.get("recipient"),
            "amount": ocr.get("amount"),
            "ref_id": ocr.get("ref_id"),
        }
        if ocr
        else None
    )
    return {
        "provider": notes.get("provider"),
        "tampering_detected": bool(notes.get("tampering_detected")),
        "tamper_signals": (notes.get("tampering") or {}).get("signals") or [],
        "template_mismatch": (notes.get("tampering") or {}).get("template_mismatch"),
        "typology": notes.get("typology") or None,
        "duplicate_evidence_of": notes.get("duplicate_evidence_of") or [],
        "ner": notes.get("ner") or None,
        "ocr": ocr_public,
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
        "upvotes": report.upvotes_count,
        "downvotes": report.downvotes_count,
        "flags": report.flags_count,
        "ai_risk_score": report.ai_risk_score,
        "ai_tampering_detected": bool(
            report.ai_forensic_notes and report.ai_forensic_notes.get("tampering_detected")
        ),
        "forensics": serialize_forensics(report.ai_forensic_notes) if published else None,
        "evidence": [
            serialize_evidence(e, public_urls.get(e.id, ""), published=published)
            for e in (evidence or [])
        ]
        if published
        else [],
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
