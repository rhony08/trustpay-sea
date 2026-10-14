"""Token family tracking: rotation + reuse detection (Doc 02 §9.2).

Each refresh token belongs to a family. On refresh: the presented jti is checked
against the family's used-set. If it was already used → REUSE → revoke the whole
family (all access/refresh tokens from that login session die).
"""

import json

import redis.asyncio as aioredis

FAMILY_TTL_SECONDS = 604800  # align with refresh TTL (7d)


class TokenFamilyStore:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    def _key(self, family: str) -> str:
        return f"auth:family:{family}"

    def _revoked_key(self, family: str) -> str:
        return f"auth:family:{family}:revoked"

    async def register(self, family: str, refresh_jti: str) -> None:
        key = self._key(family)
        pipe = self._redis.pipeline()
        pipe.sadd(key, refresh_jti)
        pipe.expire(key, FAMILY_TTL_SECONDS)
        await pipe.execute()

    async def is_used(self, family: str, refresh_jti: str) -> bool:
        return bool(await self._redis.sismember(self._key(family), refresh_jti))

    async def is_revoked(self, family: str) -> bool:
        return bool(await self._redis.exists(self._revoked_key(family)))

    async def revoke(self, family: str) -> None:
        """Kill the family: drop used-set AND leave a tombstone so leftover
        tokens from this login session can never be redeemed again."""
        pipe = self._redis.pipeline()
        pipe.delete(self._key(family))
        pipe.setex(self._revoked_key(family), FAMILY_TTL_SECONDS, "1")
        await pipe.execute()

    async def denylist_access(self, jti: str, ttl_seconds: int) -> None:
        await self._redis.setex(f"auth:jti:{jti}", ttl_seconds, "1")

    async def is_access_denied(self, jti: str) -> bool:
        return bool(await self._redis.exists(f"auth:jti:{jti}"))


def dumps(data: dict) -> str:
    return json.dumps(data, separators=(",", ":"))
