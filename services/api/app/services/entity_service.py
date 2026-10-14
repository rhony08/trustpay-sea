"""Entity service: upsert + exact-match lookup + public profile assembly.

Invariants:
- Anonymous lookups NEVER insert rows (Doc 02 §10.3 anti-poisoning). Entities
  are created on first REPORT (Phase 2) — the resolver upsert helper is only
  called from report/gov-ingestion paths.
- Lookups are exact-match on the KMS-keyed hash — no partial/ILIKE.
- Holder-name reveal follows ADR-016: these endpoints are exact-match BY
  CONSTRUCTION (caller already holds the full identifier), so the name is
  revealed with a confidence label.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import (
    EntityType,
    EntityVerificationStatus,
    HolderNameSource,
    ReportStatus,
    RiskLevel,
    Scheme,
)
from app.models import FraudReport, PaymentEntity

# Display threshold so single-user behavior can't be fingerprinted (ADR-011)
MIN_SEARCH_DISPLAY_THRESHOLD = 5

# badge driven by verification_status, not raw score (blueprint C5 fix)
_BADGE_BY_STATUS: dict[str, tuple[str, str]] = {
    EntityVerificationStatus.UNVERIFIED: ("AMBER", "Unverified"),
    EntityVerificationStatus.COMMUNITY_REPORTED: ("AMBER", "Community reported"),
    EntityVerificationStatus.ADMIN_CONFIRMED_FRAUD: ("RED", "Admin-verified fraud"),
    EntityVerificationStatus.VERIFIED_LEGIT_OWNER: ("GREEN", "Verified clean"),
    EntityVerificationStatus.GOV_BLACKLISTED: ("RED", "Government-verified fraud"),
}


async def get_entity_by_hash(db: AsyncSession, account_hash: str) -> PaymentEntity | None:
    return await db.scalar(select(PaymentEntity).where(PaymentEntity.account_hash == account_hash))


async def upsert_entity(
    db: AsyncSession,
    *,
    entity_type: EntityType,
    scheme: Scheme | str | None,
    country_code: str,
    institution_code: str | None,
    account_hash: str,
    account_masked: str,
    merchant_name: str | None = None,
    merchant_city: str | None = None,
    nmid: str | None = None,
    emvco_payload: str | None = None,
    mcc: str | None = None,
) -> PaymentEntity:
    """Called from report submission / gov ingestion — NEVER from anonymous lookups."""
    settings = get_settings()
    entity = await get_entity_by_hash(db, account_hash)
    if entity is not None:
        # refresh QR metadata if fresher data arrived
        if merchant_name and merchant_name != entity.merchant_name:
            entity.merchant_name = merchant_name
        if merchant_city and merchant_city != entity.merchant_city:
            entity.merchant_city = merchant_city
        if nmid and nmid != entity.nmid:
            entity.nmid = nmid
        if emvco_payload and emvco_payload != entity.emvco_payload:
            entity.emvco_payload = emvco_payload
        return entity

    entity = PaymentEntity(
        entity_type=entity_type,
        scheme=str(scheme) if scheme else None,
        country_code=country_code.upper(),
        institution_code=institution_code,
        account_hash=account_hash,
        hash_version=settings.account_hash_version,
        account_masked=account_masked,
        merchant_name=merchant_name,
        merchant_city=merchant_city,
        nmid=nmid,
        emvco_payload=emvco_payload,
        mcc=mcc,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


async def _report_stats(db: AsyncSession, entity_id: uuid.UUID) -> tuple[int, int, int]:
    """(total published reports, admin-verified, reports last 7d)."""
    from datetime import timedelta

    row = (
        await db.execute(
            select(
                func.count(FraudReport.id),
                func.sum(
                    (FraudReport.admin_verification_status == "APPROVED").cast(
                        __import__("sqlalchemy").Integer
                    )
                ),
            ).where(
                FraudReport.payment_entity_id == entity_id,
                FraudReport.status == ReportStatus.ACTIVE,
                FraudReport.processing_status == "PUBLISHED",
            )
        )
    ).one()
    total = int(row[0] or 0)
    verified = int(row[1] or 0)
    week_ago = datetime.now(UTC) - timedelta(days=7)
    last_7d = (
        await db.scalar(
            select(func.count(FraudReport.id)).where(
                FraudReport.payment_entity_id == entity_id,
                FraudReport.status == ReportStatus.ACTIVE,
                FraudReport.created_at >= week_ago,
            )
        )
        or 0
    )
    return int(total), int(verified or 0), int(last_7d)


def holder_name_disclosure(entity: PaymentEntity, report_count: int) -> dict | None:
    """ADR-016: exact-match surfaces only (this service is only reachable via
    exact full-account / scanned-QR endpoints)."""
    if not entity.holder_name:
        return None
    if entity.is_owner_verified or entity.holder_name_source == HolderNameSource.OWNER_KYC_PROOF:
        return {
            "name": entity.holder_name,
            "label": "Verified owner name",
            "confidence": "VERIFIED",
        }
    return {
        "name": entity.holder_name,
        "label": (f"Reported recipient name (from {report_count} reports) — verify independently"),
        "confidence": "UNVERIFIED",
    }


def build_profile(
    entity: PaymentEntity,
    *,
    total_reports: int,
    admin_verified_reports: int,
    report_velocity_7d: int,
    reports: list[dict] | None = None,
) -> dict:
    badge_color, badge_label = _BADGE_BY_STATUS.get(
        entity.verification_status, ("AMBER", "Unverified")
    )
    return {
        "entity": {
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "scheme": entity.scheme,
            "country": entity.country_code,
            "institution": entity.institution_code,
            "account_masked": entity.account_masked,
            "merchant_name": entity.merchant_name,
            "merchant_city": entity.merchant_city,
            "mcc": entity.mcc,
            "nmid": entity.nmid,
            "holder": holder_name_disclosure(entity, total_reports),
        },
        "risk_assessment": {
            "risk_score": entity.risk_score,
            "risk_level": RiskLevel.from_score(entity.risk_score).value,
            "verification_status": entity.verification_status,
            "badge": {"color": badge_color, "label": badge_label},
            "is_gov_blacklisted": entity.is_gov_blacklisted,
            "is_under_dispute": entity.is_under_dispute,
            "is_verified_legit": entity.is_owner_verified,
        },
        "community_signals": {
            "total_reports": total_reports,
            "admin_verified_reports": admin_verified_reports,
            "report_velocity_7d": report_velocity_7d,
            "total_loss_by_currency": entity.total_loss_by_currency,
        },
        "reports": reports or [],
        "in_registry": True,
    }


def not_found_profile(query: dict) -> dict:
    return {
        "status": "not_found",
        "in_registry": False,
        "query": query,
        "message": "Not yet reviewed — no reports filed for this identifier.",
    }
