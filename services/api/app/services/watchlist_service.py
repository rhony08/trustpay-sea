"""Watchlist + watcher alerts (Phase 3B.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FraudReport, PaymentEntity, WatchlistEntry
from app.services.notifications import notify_watchers as _notify_watchers


async def add_watch(db: AsyncSession, user_id: uuid.UUID, entity_id: uuid.UUID) -> WatchlistEntry:
    existing = await db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.payment_entity_id == entity_id,
        )
    )
    if existing is not None:
        return existing
    entry = WatchlistEntry(user_id=user_id, payment_entity_id=entity_id)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def remove_watch(db: AsyncSession, user_id: uuid.UUID, entity_id: uuid.UUID) -> bool:
    entry = await db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == user_id,
            WatchlistEntry.payment_entity_id == entity_id,
        )
    )
    if entry is None:
        return False
    await db.delete(entry)
    await db.commit()
    return True


async def list_watch(db: AsyncSession, user_id: uuid.UUID) -> list[WatchlistEntry]:
    rows = await db.scalars(
        select(WatchlistEntry)
        .where(WatchlistEntry.user_id == user_id)
        .order_by(WatchlistEntry.created_at.desc())
    )
    return list(rows)


async def notify_watchers(db: AsyncSession, entity: PaymentEntity, report: FraudReport) -> int:
    """Notify watchers (in-app + email) when a report publishes; skips the reporter."""
    watchers = await db.scalars(
        select(WatchlistEntry).where(
            WatchlistEntry.payment_entity_id == entity.id,
            WatchlistEntry.notify_reports.is_(True),
        )
    )
    watcher_ids = [w.user_id for w in watchers]
    return await _notify_watchers(
        db,
        watcher_ids=watcher_ids,
        reporter_user_id=report.reporter_user_id,
        entity_masked=entity.account_masked,
        entity_id=entity.id,
        report_id=report.id,
        category=report.category,
    )
