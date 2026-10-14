"""Redis-backed idempotency for retried POSTs (Doc 02 §9.4).

Stores the response body keyed by (scope, client key) with a TTL so a client
retry returns the original result instead of creating a duplicate.
"""

from __future__ import annotations

import json

from redis.asyncio import Redis

_TTL_SECONDS = 24 * 60 * 60


def _key(scope: str, client_key: str) -> str:
    return f"idem:{scope}:{client_key}"


async def get_idempotent(redis: Redis, scope: str, client_key: str) -> dict | None:
    raw = await redis.get(_key(scope, client_key))
    return json.loads(raw) if raw else None


async def store_idempotent(redis: Redis, scope: str, client_key: str, payload: dict) -> None:
    await redis.set(_key(scope, client_key), json.dumps(payload), ex=_TTL_SECONDS)
