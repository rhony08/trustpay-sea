"""Watchlist + watcher alerts (Phase 3B.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FraudReport, PaymentEntity, UserNotification, WatchlistEntry


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
    """Create an in-app notification for each watcher (skips the reporter)."""
    watchers = await db.scalars(
        select(WatchlistEntry).where(
            WatchlistEntry.payment_entity_id == entity.id,
            WatchlistEntry.notify_reports.is_(True),
        )
    )
    created = 0
    for watcher in watchers:
        if watcher.user_id == report.reporter_user_id:
            continue
        db.add(
            UserNotification(
                user_id=watcher.user_id,
                type="WATCHED_ENTITY_REPORT",
                entity_id=entity.id,
                payload={"report_id": str(report.id), "category": report.category},
            )
        )
        created += 1
    if created:
        await db.commit()
    return created
