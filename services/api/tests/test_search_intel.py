"""Search intelligence tests (Phases 3.1–3.3)."""

import uuid
from datetime import date, timedelta

from app.db import SessionLocal
from app.enums import EntityType, Scheme
from app.models import EntitySearchStat, SearchEventDaily
from app.services.entity_service import upsert_entity
from app.services.search_intel import (
    _round_display,
    get_search_intel,
    record_search,
    rollup_search_stats,
)


async def _make_entity(account: str) -> uuid.UUID:
    async with SessionLocal() as db:
        entity = await upsert_entity(
            db,
            entity_type=EntityType.BANK_ACCOUNT,
            scheme=Scheme.BANK,
            country_code="ID",
            institution_code="014",
            account_hash=uuid.uuid4().hex,
            account_masked=f"{account[:3]}-****-{account[-3:]}",
        )
    return entity.id


def test_round_display_formats() -> None:
    assert _round_display(5) == "5"
    assert _round_display(999) == "999"
    assert _round_display(1234) == "~1.2k"
    assert _round_display(2_300_000) == "~2.3M"


async def test_search_count_gated_until_threshold() -> None:
    entity_id = await _make_entity("7000000011")
    async with SessionLocal() as db:
        await record_search(db, entity_id)
        intel = await get_search_intel(db, entity_id)
    assert intel is not None
    assert intel["threshold_gated"] is True
    assert intel["total_searches"] is None

    async with SessionLocal() as db:
        for _ in range(4):
            await record_search(db, entity_id)
        intel = await get_search_intel(db, entity_id)
    assert intel["threshold_gated"] is False
    assert intel["total_searches"] == 5
    assert intel["total_searches_display"] == "5"


async def test_rollup_recomputes_windows() -> None:
    entity_id = await _make_entity("7000000022")
    today = date.today()
    async with SessionLocal() as db:
        db.add(EntitySearchStat(payment_entity_id=entity_id))
        for offset, count in [(0, 3), (3, 2), (20, 5), (60, 10)]:
            db.add(
                SearchEventDaily(
                    payment_entity_id=entity_id,
                    day=today - timedelta(days=offset),
                    search_count=count,
                )
            )
        await db.commit()
        await rollup_search_stats(db)
        stat = await db.get(EntitySearchStat, entity_id)
    assert stat.total_searches == 20
    assert stat.searches_7d == 5  # today(3) + 3d ago(2)
    assert stat.searches_30d == 10  # + 20d ago(5)
