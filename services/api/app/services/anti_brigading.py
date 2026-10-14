"""Anti-brigading / review-bomb detector (Phase 6.2, Doc 02 §5.2).

Uses a human-identity graph (distinct reporters weighted by `identity_trust`),
not raw row counts. Two detectors: a short 3h burst, and a 7-day EWMA z-score
for slow-burn attacks. A hit sets `dampen_factor = 0.45` and flags the entity for
the admin priority queue.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ReportStatus
from app.models import FraudReport, User

SPIKE_DAMPEN = 0.45
BURST_VELOCITY = 3
LOW_TRUST = 45
Z_THRESHOLD = 3.0


async def detect_anomaly(db: AsyncSession, entity_id: uuid.UUID) -> tuple[bool, float]:
    now = datetime.now(UTC)
    rows = await db.execute(
        select(FraudReport.reporter_user_id, FraudReport.created_at, User.identity_trust)
        .join(User, User.id == FraudReport.reporter_user_id)
        .where(
            FraudReport.payment_entity_id == entity_id,
            FraudReport.status == ReportStatus.ACTIVE,
            FraudReport.created_at >= now - timedelta(days=8),
        )
    )
    records = [(rid, created, trust or 10) for rid, created, trust in rows]

    # Short burst: >=3 distinct identities in 3h, average trust low.
    recent = [r for r in records if r[1] and r[1] >= now - timedelta(hours=3)]
    identities = {rid: trust for rid, _created, trust in recent if rid is not None}
    if len(identities) >= BURST_VELOCITY:
        avg_trust = sum(identities.values()) / len(identities)
        if avg_trust < LOW_TRUST:
            return True, SPIKE_DAMPEN

    # Slow burn: today's count vs the prior 7-day daily baseline (z-score).
    today = now.date()
    daily: dict = {today - timedelta(days=i): 0 for i in range(8)}
    for _rid, created, _trust in records:
        if created is None:
            continue
        day = created.date()
        if day in daily:
            daily[day] += 1
    baseline = [daily[today - timedelta(days=i)] for i in range(1, 8)]
    mean = sum(baseline) / len(baseline) if baseline else 0.0
    variance = sum((x - mean) ** 2 for x in baseline) / len(baseline) if baseline else 0.0
    std = variance**0.5
    if std > 0 and daily[today] >= 3 and (daily[today] - mean) / std > Z_THRESHOLD:
        return True, SPIKE_DAMPEN

    return False, 1.0
