"""Grounding + fact-check + unicode/homoglyph tests (Phases 3.4–3.7)."""

import uuid

import redis.asyncio as aioredis

from app.ai import factcheck
from app.ai.summary import build_entity_summary, summary_is_grounded
from app.config import get_settings
from app.resolver.emvco import has_homoglyph_risk, normalize_merchant_name
from app.services.intel_service import _cached_summary


def test_summary_is_grounded_in_facts() -> None:
    facts = {
        "entity_label": "merchant Toko ABC",
        "total_reports": 4,
        "admin_verified_reports": 1,
        "first_reported_at": "2026-03-02T00:00:00Z",
        "report_velocity_7d": 2,
        "is_gov_blacklisted": False,
        "is_under_dispute": True,
    }
    text = build_entity_summary(facts)
    assert "Toko ABC" in text and "4" in text
    assert summary_is_grounded(text, facts) is True


def test_summary_grounding_rejects_hallucinated_number() -> None:
    assert summary_is_grounded("This entity has 99 reports.", {"total_reports": 1}) is False


def test_grounding_check_accepts_date_digits() -> None:
    facts = {"entity_label": "x", "total_reports": 1, "first_reported_at": "2026-03-02T00:00:00Z"}
    text = build_entity_summary(facts)
    assert "2026-03-02"[:10] in text
    assert summary_is_grounded(text, facts) is True


async def test_factcheck_keyless_returns_empty() -> None:
    assert await factcheck.lookup_fact_checks("any merchant") == []


def test_normalize_merchant_name_folds_fullwidth_and_strips_zero_width() -> None:
    assert normalize_merchant_name("ＡＢＣ") == "ABC"
    assert normalize_merchant_name("Toko\u200b ABC") == "Toko ABC"


def test_homoglyph_detector_flags_zero_width_and_cyrillic() -> None:
    assert has_homoglyph_risk("Toko\u200bABC") is True
    assert has_homoglyph_risk("Toko АВС") is True  # Cyrillic А В С
    assert has_homoglyph_risk("Toko ABC") is False


async def test_summary_cache_hits_second_time() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    entity_id = uuid.uuid4()
    facts = {"entity_label": "x", "total_reports": 2, "admin_verified_reports": 0}
    try:
        first = await _cached_summary(redis, entity_id, facts)
        second = await _cached_summary(redis, entity_id, facts)
    finally:
        await redis.aclose()
    assert first["cached"] is False
    assert second["cached"] is True
    assert first["text"] == second["text"]
