"""Cross-wallet e-wallet phone search tests (Phase 11)."""

import httpx
import pytest
import redis.asyncio as aioredis

from app.config import get_settings

PASSWORD = "s3cure-Passw0rd"


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    await redis.aclose()


async def _token(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _report(
    client: httpx.AsyncClient, token: str, country: str, bank: str, account: str
) -> None:
    resp = await client.post(
        "/api/v1/reports",
        json={
            "target": {"kind": "ACCOUNT", "country": country, "bank": bank, "account": account},
            "category": "INVESTMENT_PIG_BUTCHERING",
            "severity": 4,
            "description": "Phone-based e-wallet scam reported by the victim.",
            "consent": True,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 202, resp.text


async def test_phone_search_aggregates_across_wallets(client: httpx.AsyncClient) -> None:
    token = await _token(client, "phonesearch@trustpay.dev")
    phone = "081298765432"
    await _report(client, token, "ID", "GOPAY", phone)
    await _report(client, token, "ID", "OVO", phone)

    resp = await client.get("/api/v1/entities/phone", params={"country": "ID", "phone": phone})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["wallet_count"] == 2
    codes = {w["institution"] for w in data["wallets"]}
    assert codes == {"GOPAY", "OVO"}
    assert data["phone_masked"] == "***5432"
    assert data["totals"]["total_reports"] >= 0


async def test_phone_search_ignores_bank_accounts(client: httpx.AsyncClient) -> None:
    token = await _token(client, "phonebank@trustpay.dev")
    phone = "0812987654"  # 10 digits — valid BCA length too
    await _report(client, token, "ID", "014", phone)  # bank account, not an e-wallet

    resp = await client.get("/api/v1/entities/phone", params={"country": "ID", "phone": phone})
    assert resp.json()["data"]["wallet_count"] == 0
    assert resp.json()["status"] == "not_found"


async def test_phone_search_unknown(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/entities/phone", params={"country": "ID", "phone": "081200000000"}
    )
    assert resp.json()["status"] == "not_found"
    assert resp.json()["data"]["wallets"] == []


async def test_screen_phone_visitor_buckets_counts(client: httpx.AsyncClient) -> None:
    token = await _token(client, "screenphone@trustpay.dev")
    phone = "081211112222"
    await _report(client, token, "ID", "GOPAY", phone)

    resp = await client.get("/api/v1/screen/phone", params={"country": "ID", "phone": phone})
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-TrustPay-Tier"] == "VISITOR"
    data = resp.json()["data"]
    assert data["wallets"][0]["total_reports"] == "<10"  # bucketed for visitors
