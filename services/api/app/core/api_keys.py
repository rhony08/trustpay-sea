"""Public screen-API keys: generation, verification, quotas, probe detection.

Implements docs/09 tiers. Raw keys are shown once; only the SHA-256 hash + last-4
are stored. Quotas reset at midnight Asia/Jakarta (WIB). Anti-probing counts the
distinct entities a caller screens per hour.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import ApiKeyTier
from app.models import ApiKey

WIB = timezone(timedelta(hours=7))

VISITOR_TIER = "VISITOR"


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key(prefix: str) -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, last4)."""
    raw = f"{prefix}{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw), raw[-4:]


def daily_limit(tier: str) -> int | None:
    settings = get_settings()
    return {
        ApiKeyTier.DEMO.value: settings.screen_demo_daily_limit,
        ApiKeyTier.PARTNER.value: settings.screen_partner_daily_limit,
        ApiKeyTier.ENTERPRISE.value: None,  # unlimited
        VISITOR_TIER: settings.screen_visitor_daily_limit,
    }.get(tier, settings.screen_demo_daily_limit)


async def lookup_api_key(db: AsyncSession, raw: str) -> ApiKey | None:
    if not raw:
        return None
    return await db.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == hash_api_key(raw),
            ApiKey.is_active.is_(True),
        )
    )


async def consume_quota(
    redis: Redis, *, identity: str, limit: int | None
) -> tuple[bool, int | None, int | None]:
    """Returns (allowed, remaining, limit). None limit = unlimited."""
    if limit is None:
        return True, None, None
    now = datetime.now(WIB)
    key = f"screenq:{identity}:{now:%Y%m%d}"
    count = await redis.incr(key)
    if count == 1:
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await redis.expireat(key, int(midnight.timestamp()))
    return count <= limit, max(0, limit - count), limit


async def distinct_entities_this_hour(redis: Redis, *, identity: str, entity_ref: str) -> int:
    now = datetime.now(WIB)
    key = f"screenprobe:{identity}:{now:%Y%m%d%H}"
    await redis.sadd(key, entity_ref)
    await redis.expire(key, 7200)
    return int(await redis.scard(key))


@dataclass
class ScreenCaller:
    tier: str
    identity: str
    limit: int | None
    remaining: int | None
    api_key: ApiKey | None = None

    @property
    def keyed(self) -> bool:
        return self.api_key is not None


def now_utc() -> datetime:
    return datetime.now(UTC)
