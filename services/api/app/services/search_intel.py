"""Search intelligence (Phase 3.1–3.2).

Records a search on every lookup hit and exposes rounded, threshold-gated
popularity signals so single-user behaviour cannot be fingerprinted. The daily
rollup job compacts `search_events_daily` into the 7d/30d/total windows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntitySearchStat, SearchEventDaily

# Under this many searches we never expose an exact count (Doc 02 §3.2 ADR-011).
MIN_SEARCH_DISPLAY_THRESHOLD = 5


async def record_search(db: AsyncSession, entity_id: uuid.UUID) -> None:
    """Increment today's daily counter + the entity's total. Cheap upserts."""
    now = datetime.now(UTC)
    today = now.date()

    daily = pg_insert(SearchEventDaily).values(
        payment_entity_id=entity_id, day=today, search_count=1
    )
    daily = daily.on_conflict_do_update(
        index_elements=["payment_entity_id", "day"],
        set_={"search_count": SearchEventDaily.search_count + 1},
    )
    await db.execute(daily)

    stats = pg_insert(EntitySearchStat).values(
        payment_entity_id=entity_id,
        total_searches=1,
        searches_7d=0,
        searches_30d=0,
        last_searched_at=now,
        updated_at=now,
    )
    stats = stats.on_conflict_do_update(
        index_elements=["payment_entity_id"],
        set_={
            "total_searches": EntitySearchStat.total_searches + 1,
            "last_searched_at": now,
            "updated_at": now,
        },
    )
    await db.execute(stats)
    await db.commit()


async def get_search_intel(db: AsyncSession, entity_id: uuid.UUID) -> dict | None:
    stat = await db.get(EntitySearchStat, entity_id)
    if stat is None:
        return None
    gated = stat.total_searches < MIN_SEARCH_DISPLAY_THRESHOLD
    return {
        "total_searches": None if gated else stat.total_searches,
        "total_searches_display": None if gated else _round_display(stat.total_searches),
        "searches_7d": stat.searches_7d,
        "searches_30d": stat.searches_30d,
        "last_searched_at": stat.last_searched_at.isoformat() if stat.last_searched_at else None,
        "threshold_gated": gated,
    }


def _round_display(count: int) -> str:
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"~{count / 1000:.1f}k"
    return f"~{count / 1_000_000:.1f}M"


async def rollup_search_stats(db: AsyncSession, *, limit: int = 5000) -> int:
    """Recompute 7d/30d windows for entities from `search_events_daily`."""
    today = date.today()
    week_ago = today - timedelta(days=6)
    month_ago = today - timedelta(days=29)

    rows = list(await db.scalars(select(EntitySearchStat).limit(limit)))

    async def _sum(entity_id: uuid.UUID, since: date | None) -> int:
        stmt = select(func.coalesce(func.sum(SearchEventDaily.search_count), 0)).where(
            SearchEventDaily.payment_entity_id == entity_id
        )
        if since is not None:
            stmt = stmt.where(SearchEventDaily.day >= since)
        return int(await db.scalar(stmt) or 0)

    for stat in rows:
        stat.total_searches = await _sum(stat.payment_entity_id, None)
        stat.searches_7d = await _sum(stat.payment_entity_id, week_ago)
        stat.searches_30d = await _sum(stat.payment_entity_id, month_ago)
    await db.commit()
    return len(rows)
