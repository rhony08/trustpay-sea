"""Token-bucket rate limiter — hammering past capacity → 429 (Phase 0.4 AC)."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_rate_limit_429_after_capacity(jwt_keypair) -> None:
    import os

    os.environ["RATE_LIMIT_ENABLED"] = "true"
    os.environ["RATE_LIMIT_CAPACITY"] = "5"
    os.environ["RATE_LIMIT_REFILL_PER_MINUTE"] = "5"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        statuses = []
        for _ in range(8):
            resp = await client.get("/healthz")
            statuses.append(resp.status_code)
        # first 5 pass, then 429s
        assert statuses[:5] == [200] * 5
        assert 429 in statuses

    get_settings.cache_clear()
    os.environ["RATE_LIMIT_CAPACITY"] = "60"
    os.environ["RATE_LIMIT_REFILL_PER_MINUTE"] = "60"
    get_settings.cache_clear()
    # flush polluted buckets so later tests don't inherit a near-empty token bucket
    import redis.asyncio as aioredis

    from app.config import get_settings as gs

    r = aioredis.from_url(gs().redis_url, decode_responses=True)
    async for key in r.scan_iter("rl:*"):
        await r.delete(key)
    await r.aclose()
