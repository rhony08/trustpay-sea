"""Explainable risk scorer (Phase 6.1–6.4, Doc 02 §5.1).

R = clamp(R_base + Δ_gov + 35·N_admin_verified + Σcommunity·dampen + Δ_forensics
          − Δ_merchant_kyc − Δ_resolution, 0, 100)

Persists the score + factor breakdown on the entity. Gov listings override to
100; the dispute freeze is rise-only (never lowers an existing score).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AdminVerificationStatus, ProcessingStatus, ReportStatus, RiskLevel
from app.models import FraudReport, PaymentEntity
from app.services.anti_brigading import detect_anomaly
from app.services.dispute_service import apply_dispute_cap

R_BASE = 15
ADMIN_VERIFIED_WEIGHT = 35
FORENSICS_BONUS = 20
MERCHANT_KYC_DISCOUNT = -20
SETTLEMENT_DISCOUNT = -15
GOV_OVERRIDE = 100


@dataclass
class RiskResult:
    score: int
    level: str
    factors: list[dict] = field(default_factory=list)
    dispute_hold: bool = False
    anomaly_spike: bool = False
    dampen: float = 1.0


async def _count(db: AsyncSession, entity_id, status) -> int:
    return int(
        await db.scalar(
            select(func.count(FraudReport.id)).where(
                FraudReport.payment_entity_id == entity_id,
                FraudReport.status == status,
                FraudReport.processing_status == ProcessingStatus.PUBLISHED,
            )
        )
        or 0
    )


async def compute_risk(db: AsyncSession, entity: PaymentEntity) -> RiskResult:
    reports = list(
        await db.scalars(
            select(FraudReport).where(
                FraudReport.payment_entity_id == entity.id,
                FraudReport.status == ReportStatus.ACTIVE,
                FraudReport.processing_status == ProcessingStatus.PUBLISHED,
            )
        )
    )
    admin_verified = sum(
        1 for r in reports if r.admin_verification_status == AdminVerificationStatus.APPROVED
    )
    community = sum(10 * r.severity + 2 * min(10, r.upvotes_count or 0) for r in reports)
    forensics = (
        FORENSICS_BONUS
        if any((r.ai_forensic_notes or {}).get("tampering_detected") for r in reports)
        else 0
    )
    settled = await _count(db, entity.id, ReportStatus.RESOLVED_BY_SETTLEMENT)
    anomaly, dampen = await detect_anomaly(db, entity.id)
    community_dampened = round(community * dampen)

    merchant_kyc = (
        MERCHANT_KYC_DISCOUNT if entity.is_owner_verified and not entity.is_gov_blacklisted else 0
    )
    resolution = SETTLEMENT_DISCOUNT if settled else 0
    gov = GOV_OVERRIDE if entity.is_gov_blacklisted else 0

    factors = [
        {"label": "base", "weight": R_BASE},
        {"label": "gov_blacklist", "weight": gov},
        {"label": "admin_verified", "weight": ADMIN_VERIFIED_WEIGHT * admin_verified},
        {"label": "community", "weight": community_dampened, "dampened": anomaly},
        {"label": "forensics", "weight": forensics},
        {"label": "merchant_kyc", "weight": merchant_kyc},
        {"label": "resolution", "weight": resolution},
    ]

    if entity.is_gov_blacklisted:
        score = GOV_OVERRIDE
    else:
        raw = (
            R_BASE
            + gov
            + ADMIN_VERIFIED_WEIGHT * admin_verified
            + community_dampened
            + forensics
            + merchant_kyc
            + resolution
        )
        score = max(0, min(100, round(raw)))
        score = apply_dispute_cap(entity, score)

    return RiskResult(
        score=score,
        level=RiskLevel.from_score(score).value,
        factors=factors,
        dispute_hold=entity.is_under_dispute,
        anomaly_spike=anomaly,
        dampen=dampen,
    )


async def recompute_entity_score(db: AsyncSession, entity: PaymentEntity) -> RiskResult:
    result = await compute_risk(db, entity)
    entity.risk_score = result.score
    entity.anomaly_spike_detected = result.anomaly_spike
    entity.dampen_factor = Decimal(str(result.dampen))
    entity.risk_factors = {"factors": result.factors, "dispute_hold": result.dispute_hold}
    await db.commit()
    await db.refresh(entity)
    return result
