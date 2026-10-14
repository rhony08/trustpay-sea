"""Token-bucket rate limiter (Redis, atomic Lua) — ADR-007 / Doc 02 §9.5.

Limit defined as capacity=refill tokens, refilled continuously at
refill_per_minute / 60 tokens per second. Keys are scoped per bucket
(e.g. "anon", "apikey:<id>") and identified by client (IP / API key).
"""

from fastapi import Request, Response, status
from redis.asyncio import Redis

from app.config import get_settings

_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_minute = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end

local elapsed = math.max(0, now - ts)
local refill = elapsed * (refill_per_minute / 60.0)
tokens = math.min(capacity, tokens + refill)

local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, 120)
return {allowed, tokens}
"""


class RateLimiter:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._script = redis.register_script(_BUCKET_LUA)

    async def hit(self, scope: str, identity: str, *, cost: int = 1) -> tuple[bool, float]:
        settings = get_settings()
        import time

        key = f"rl:{scope}:{identity}"
        result = await self._script(
            keys=[key],
            args=[
                settings.rate_limit_capacity,
                settings.rate_limit_refill_per_minute,
                time.time(),
                cost,
            ],
        )
        allowed = bool(int(result[0]))
        return allowed, float(result[1])


async def enforce_rate_limit(request: Request, response: Response) -> None:
    """FastAPI dependency: anonymous/IP token bucket on every route."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    limiter = RateLimiter(request.app.state.redis)
    identity = request.client.host if request.client else "unknown"
    allowed, _remaining = await limiter.hit("anon", identity)
    if not allowed:
        raise _too_many()


def _too_many() -> Exception:
    from fastapi import HTTPException

    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "rate limit exceeded",
        headers={"Retry-After": "60"},
    )
