"""Cross-wallet e-wallet search by phone number (Phase 11).

A phone number typically maps to many e-wallets; users shouldn't have to check
each wallet type separately. Entities written for an e-wallet carry a
`phone_hash`, so this aggregates every wallet for that phone into one result.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import EntityType, RiskLevel
from app.models import PaymentEntity
from app.resolver.banks import institutions_for_country
from app.resolver.normalize import normalize_phone
from app.services.entity_service import _report_stats


async def search_phone(db: AsyncSession, *, country: str, phone: str) -> dict:
    settings = get_settings()
    phone_hash, phone_masked = normalize_phone(
        country=country, phone=phone, kms_key=settings.account_hmac_key
    )
    entities = list(
        await db.scalars(
            select(PaymentEntity).where(
                PaymentEntity.phone_hash == phone_hash,
                PaymentEntity.country_code == country.upper(),
                PaymentEntity.entity_type == EntityType.BANK_ACCOUNT.value,
            )
        )
    )
    names = {i.code: i.name for i in institutions_for_country(country)}

    wallets: list[dict] = []
    total_reports = 0
    max_score = 0
    for entity in entities:
        count, _verified, _velocity = await _report_stats(db, entity.id)
        total_reports += count
        max_score = max(max_score, entity.risk_score)
        wallets.append(
            {
                "institution": entity.institution_code,
                "institution_name": names.get(
                    entity.institution_code or "", entity.institution_code
                ),
                "account_masked": entity.account_masked,
                "risk_score": entity.risk_score,
                "risk_level": RiskLevel.from_score(entity.risk_score).value,
                "total_reports": count,
                "is_gov_blacklisted": entity.is_gov_blacklisted,
                "is_under_dispute": entity.is_under_dispute,
            }
        )
    wallets.sort(key=lambda w: (-w["risk_score"], w["institution_name"] or ""))

    return {
        "country": country.upper(),
        "phone_masked": phone_masked,
        "wallet_count": len(wallets),
        "wallets": wallets,
        "totals": {"total_reports": total_reports, "max_risk_score": max_score},
        "risk_level": RiskLevel.from_score(max_score).value,
    }
