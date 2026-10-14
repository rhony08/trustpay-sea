"""Entity intelligence assembly (Phase 3): search stats + grounded summary + fact-checks."""

from __future__ import annotations

import hashlib
import json
import uuid

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import factcheck
from app.ai.summary import build_entity_summary, summary_is_grounded
from app.config import get_settings
from app.enums import ProcessingStatus, ReportStatus
from app.models import FraudReport, PaymentEntity
from app.services.search_intel import get_search_intel


def _entity_label(entity: PaymentEntity) -> str:
    if entity.merchant_name:
        return f"merchant {entity.merchant_name}"
    return f"{entity.institution_code or entity.entity_type} account"


async def _first_reported_at(db: AsyncSession, entity_id: uuid.UUID) -> str | None:
    value = await db.scalar(
        select(func.min(FraudReport.created_at)).where(
            FraudReport.payment_entity_id == entity_id,
            FraudReport.status == ReportStatus.ACTIVE,
            FraudReport.processing_status == ProcessingStatus.PUBLISHED,
        )
    )
    return value.isoformat() if value else None


async def _cached_summary(redis: Redis, entity_id: uuid.UUID, facts: dict) -> dict:
    settings = get_settings()
    text = build_entity_summary(facts)
    version = hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()[
        :16
    ]
    key = f"aisum:{entity_id}"
    if await redis.get(f"{key}:ver") == version:
        cached = await redis.get(key)
        if cached is not None:
            return {"text": cached, "cached": True, "grounded": True}
    ttl = settings.ai_summary_cache_ttl_seconds
    await redis.set(key, text, ex=ttl)
    await redis.set(f"{key}:ver", version, ex=ttl)
    return {"text": text, "cached": False, "grounded": summary_is_grounded(text, facts)}


async def get_entity_intel(
    db: AsyncSession,
    redis: Redis,
    entity: PaymentEntity,
    *,
    total_reports: int,
    admin_verified_reports: int,
    report_velocity_7d: int,
) -> dict:
    facts = {
        "entity_label": _entity_label(entity),
        "entity_type": entity.entity_type,
        "country": entity.country_code,
        "total_reports": total_reports,
        "admin_verified_reports": admin_verified_reports,
        "report_velocity_7d": report_velocity_7d,
        "first_reported_at": await _first_reported_at(db, entity.id),
        "is_gov_blacklisted": entity.is_gov_blacklisted,
        "is_under_dispute": entity.is_under_dispute,
    }
    query = entity.merchant_name or entity.institution_code or ""
    return {
        "ai_summary": await _cached_summary(redis, entity.id, facts),
        "related_fact_checks": await factcheck.lookup_fact_checks(query),
        "search_intelligence": await get_search_intel(db, entity.id),
    }
