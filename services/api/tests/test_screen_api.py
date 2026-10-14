"""Public Screen API + key management tests (Phase 9 / docs/09)."""

import hashlib
from datetime import datetime

import httpx
import pytest
import redis.asyncio as aioredis

from app.config import get_settings
from app.core.api_keys import WIB

PASSWORD = "s3cure-Passw0rd"


@pytest.fixture(autouse=True)
async def _flush_redis() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    async for key in redis.scan_iter("screenq:*"):
        await redis.delete(key)
    async for key in redis.scan_iter("screenprobe:*"):
        await redis.delete(key)
    await redis.aclose()


async def _signup(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_account(client: httpx.AsyncClient, account: str) -> None:
    token = await _signup(client, f"seed-{account}@trustpay.dev")
    resp = await client.post(
        "/api/v1/reports",
        json={
            "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
            "category": "ONLINE_SHOP_GHOSTING",
            "severity": 3,
            "description": "Seeded account for screen-API tests.",
            "consent": True,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 202, resp.text


async def _issue_key(client: httpx.AsyncClient, token: str, tier: str = "DEMO") -> str:
    resp = await client.post(
        "/api/v1/keys", json={"name": "test", "tier": tier}, headers=_auth(token)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["api_key"]


async def test_visitor_screen_is_masked_and_bucketed(client: httpx.AsyncClient) -> None:
    await _seed_account(client, "8600000001")
    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000001"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-TrustPay-Tier"] == "VISITOR"
    assert resp.headers["X-RateLimit-Limit"] == "20"
    body = resp.json()
    assert body["status"] == "success"
    entity = body["data"]["entity"]
    assert entity["account_masked"]
    assert "holder" not in entity  # no PII via the public API
    assert body["data"]["signals"]["total_reports"] == "<10"  # bucketed for visitors
    assert "search_intelligence" not in body["data"]


async def test_visitor_not_found(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8699999999"},
    )
    assert resp.json()["status"] == "not_found"
    assert resp.json()["data"]["in_registry"] is False


async def test_keyed_screen_gets_exact_counts_and_intel(client: httpx.AsyncClient) -> None:
    await _seed_account(client, "8600000002")
    token = await _signup(client, "keyed@trustpay.dev")
    raw = await _issue_key(client, token)

    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000002"},
        headers={"X-API-Key": raw},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-TrustPay-Tier"] == "DEMO"
    data = resp.json()["data"]
    assert isinstance(data["signals"]["total_reports"], int)
    assert "search_intelligence" in data
    assert data["note"].startswith("Risk score")


async def test_invalid_key_401(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000003"},
        headers={"X-API-Key": "tpk_live_bogus"},
    )
    assert resp.status_code == 401


async def test_partner_key_requires_admin(client: httpx.AsyncClient) -> None:
    user = await _signup(client, "pleb@trustpay.dev")
    denied = await client.post("/api/v1/keys", json={"tier": "PARTNER"}, headers=_auth(user))
    assert denied.status_code == 403

    admin = await _signup(client, "partner-admin@trustpay.dev")
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    async with SessionLocal() as db:
        row = await db.scalar(select(User).where(User.email == "partner-admin@trustpay.dev"))
        row.role = "ANALYST"
        await db.commit()
    ok = await client.post("/api/v1/keys", json={"tier": "PARTNER"}, headers=_auth(admin))
    assert ok.status_code == 201
    assert "reports:write" in ok.json()["data"]["scopes"]


async def test_key_quota_exceeded(client: httpx.AsyncClient) -> None:
    await _seed_account(client, "8600000004")
    token = await _signup(client, "quota-key@trustpay.dev")
    raw = await _issue_key(client, token)

    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    today = datetime.now(WIB).strftime("%Y%m%d")
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    await redis.set(f"screenq:key:{key_hash}:{today}", get_settings().screen_demo_daily_limit)
    await redis.aclose()

    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000004"},
        headers={"X-API-Key": raw},
    )
    assert resp.status_code == 429


async def test_revoke_makes_key_invalid(client: httpx.AsyncClient) -> None:
    await _seed_account(client, "8600000005")
    token = await _signup(client, "revoke-key@trustpay.dev")
    created = await client.post("/api/v1/keys", json={}, headers=_auth(token))
    key_id = created.json()["data"]["id"]
    raw = created.json()["data"]["api_key"]

    await client.delete(f"/api/v1/keys/{key_id}", headers=_auth(token))
    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000005"},
        headers={"X-API-Key": raw},
    )
    assert resp.status_code == 401


async def test_rotate_invalidates_old_key(client: httpx.AsyncClient) -> None:
    await _seed_account(client, "8600000006")
    token = await _signup(client, "rotate-key@trustpay.dev")
    created = await client.post("/api/v1/keys", json={}, headers=_auth(token))
    key_id = created.json()["data"]["id"]
    old_raw = created.json()["data"]["api_key"]

    rotated = await client.post(f"/api/v1/keys/{key_id}/rotate", headers=_auth(token))
    new_raw = rotated.json()["data"]["api_key"]
    assert new_raw != old_raw

    params = {"country": "ID", "bank": "014", "account": "8600000006"}
    assert (
        await client.get("/api/v1/screen/account", params=params, headers={"X-API-Key": old_raw})
    ).status_code == 401
    assert (
        await client.get("/api/v1/screen/account", params=params, headers={"X-API-Key": new_raw})
    ).status_code == 200


async def test_probe_pattern_triggers_challenge(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_account(client, "8600000007")
    settings = get_settings()
    monkeypatch.setattr(settings, "screen_probe_visitor_distinct_per_hour", 0)

    resp = await client.get(
        "/api/v1/screen/account",
        params={"country": "ID", "bank": "014", "account": "8600000007"},
    )
    assert resp.status_code == 429
    assert resp.headers.get("X-Challenge-Required") == "true"
