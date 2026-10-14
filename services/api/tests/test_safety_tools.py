"""Security-awareness tools + DSAR tests (Phase 4B)."""

import httpx
import pytest
import redis.asyncio as aioredis

from app.config import get_settings
from app.db import SessionLocal
from app.models import FraudReport

PASSWORD = "s3cure-Passw0rd"


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    async for key in redis.scan_iter("flagrate:*"):
        await redis.delete(key)
    await redis.aclose()


async def _signup(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _report_body(account: str) -> dict:
    return {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Seller took payment and vanished without shipping anything.",
        "consent": True,
    }


async def test_too_good_checker_flags_bait(client: httpx.AsyncClient) -> None:
    bait = await client.post(
        "/api/v1/tools/too-good-to-be-true",
        json={"text": "Guaranteed profit! Deposit now and double your money today only!"},
    )
    data = bait.json()["data"]
    assert data["suspicious"] is True
    assert data["score"] > 0
    assert any(s["code"] == "guaranteed_returns" for s in data["signals"])

    benign = await client.post(
        "/api/v1/tools/too-good-to-be-true",
        json={"text": "Thanks for your order, it ships tomorrow."},
    )
    assert benign.json()["data"]["suspicious"] is False


async def test_hotlines_by_country(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/hotlines", params={"country": "ID"})
    numbers = [h.get("number") for h in resp.json()["data"]["hotlines"]]
    assert "110" in numbers
    assert (await client.get("/api/v1/hotlines", params={"country": "US"})).json()["data"][
        "hotlines"
    ] == []


async def test_recovery_plan(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/recovery", params={"country": "MY", "bank": "MBB"})
    data = resp.json()["data"]
    assert data["immediate_steps"]
    assert data["referral"]["url"]


async def test_warning_card_signed_link(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "warncard@trustpay.dev")
    await client.post("/api/v1/reports", json=_report_body("8400000001"), headers=_auth(token))

    card = await client.get(
        "/api/v1/tools/warning-card",
        params={"country": "ID", "bank": "014", "account": "8400000001"},
    )
    assert card.status_code == 200, card.text
    assert card.json()["data"]["share_path"].startswith("/warning?token=")

    missing = await client.get(
        "/api/v1/tools/warning-card",
        params={"country": "ID", "bank": "014", "account": "8499999999"},
    )
    assert missing.status_code == 404


async def test_dsar_export_and_erase(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "dsar@trustpay.dev")
    created = await client.post(
        "/api/v1/reports", json=_report_body("8400000002"), headers=_auth(token)
    )
    report_id = created.json()["data"]["report_id"]
    await client.post(f"/api/v1/reports/{report_id}/vote", json={"vote": 1}, headers=_auth(token))

    export = (await client.get("/api/v1/profile/export", headers=_auth(token))).json()["data"]
    assert len(export["reports"]) == 1
    assert export["reports"][0]["account_masked"].startswith("840")

    erased = (await client.delete("/api/v1/profile/data", headers=_auth(token))).json()["data"]
    assert erased["reports_deleted"] >= 1
    assert erased["votes_deleted"] >= 1

    assert (await client.get(f"/api/v1/reports/{report_id}")).status_code == 404
    import uuid

    async with SessionLocal() as db:
        assert await db.get(FraudReport, uuid.UUID(report_id)) is None
