"""Phone verification OTP (Phase 3B.2) — Redis-backed, dev-friendly.

Production swaps the delivery channel (SMS provider) for a signed link/OTP; the
verify contract (start → confirm) stays the same. Codes are short-lived.
"""

from __future__ import annotations

import secrets

from redis.asyncio import Redis

_TTL_SECONDS = 300


def _key(scope: str, subject: str) -> str:
    return f"otp:{scope}:{subject}"


async def start_otp(redis: Redis, subject: str, *, scope: str = "phone") -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.set(_key(scope, subject), code, ex=_TTL_SECONDS)
    return code


async def confirm_otp(redis: Redis, subject: str, code: str, *, scope: str = "phone") -> bool:
    stored = await redis.get(_key(scope, subject))
    if stored and stored == code:
        await redis.delete(_key(scope, subject))
        return True
    return False
