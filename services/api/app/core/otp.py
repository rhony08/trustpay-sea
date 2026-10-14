"""Phone verification OTP (Phase 3B.2) — Redis-backed, dev-friendly.

Production swaps the delivery channel (SMS provider) for a signed link/OTP; the
verify contract (start → confirm) stays the same. Codes are short-lived.
"""

from __future__ import annotations

import secrets

from redis.asyncio import Redis

_TTL_SECONDS = 300


def _key(user_id: str) -> str:
    return f"otp:phone:{user_id}"


async def start_otp(redis: Redis, user_id: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.set(_key(user_id), code, ex=_TTL_SECONDS)
    return code


async def confirm_otp(redis: Redis, user_id: str, code: str) -> bool:
    stored = await redis.get(_key(user_id))
    if stored and stored == code:
        await redis.delete(_key(user_id))
        return True
    return False
