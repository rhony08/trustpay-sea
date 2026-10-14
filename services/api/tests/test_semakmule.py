"""PDRM Semak Mule adapter tests (Malaysia gov checker)."""

import json

import httpx
import pytest
import redis.asyncio as aioredis

from app.config import Settings, get_settings
from app.services.semakmule import (
    GovCheckResult,
    SemakMuleClient,
    infer_category,
    looks_like_phone,
    parse_response,
    reset_semakmule_client,
)

PAYLOAD = {
    "status": 1,
    "status_message": "Success.",
    "table_header": ["No. Akaun", "Repot"],
    "table_data": [["123123123", 1]],
    "count": 39,
    "cat": 1,
    "kw": "123123123",
}


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    reset_semakmule_client()
    await redis.aclose()


class _FakeSemakMule:
    enabled = True

    def __init__(self) -> None:
        self.last_category: str | None = None

    async def check(self, *, category: str, value: str) -> GovCheckResult:
        self.last_category = category
        return GovCheckResult(
            available=True,
            found=True,
            report_count=1,
            reports=[{"value": value, "report_count": 1}],
            status_message="Success.",
        )


def test_infer_category_bank_vs_phone() -> None:
    assert infer_category(bank_type="COMMERCIAL", value="123123123") == "bank"
    assert infer_category(bank_type="E_WALLET", value="60123456789") == "phone"
    assert infer_category(bank_type=None, value="0123456789") == "phone"


def test_looks_like_phone() -> None:
    assert looks_like_phone("+60123456789") is True
    assert looks_like_phone("012-345 6789") is True
    assert looks_like_phone("123123123") is False


def test_parse_response_reported_account() -> None:
    result = parse_response(PAYLOAD)
    assert result.available is True
    assert result.found is True
    assert result.report_count == 1
    assert result.reports == [{"value": "123123123", "report_count": 1}]


def test_parse_response_clean_account() -> None:
    result = parse_response({"status": 1, "table_data": [], "count": 0})
    assert result.found is False
    assert result.report_count == 0


async def test_client_sends_apikey_and_parses() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["apikey"] = request.headers.get("apikey")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=PAYLOAD)

    settings = Settings(semakmule_api_key="test-key", semakmule_base_url="https://example.test/x")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SemakMuleClient(settings, http=http)
        result = await client.check_bank("123123123")

    assert captured["apikey"] == "test-key"
    assert captured["body"]["data"]["bankAccount"] == "123123123"
    assert captured["body"]["data"]["category"] == "bank"
    assert result.found is True


async def test_client_disabled_without_key() -> None:
    client = SemakMuleClient(Settings(semakmule_api_key=None))
    assert client.enabled is False
    result = await client.check_bank("123")
    assert result.available is False
    assert result.found is False


async def test_client_degrades_on_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    settings = Settings(semakmule_api_key="k", semakmule_base_url="https://example.test/x")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SemakMuleClient(settings, http=http)
        result = await client.check_bank("123")
    assert result.available is False
    assert result.found is False


async def test_my_account_lookup_includes_gov_check(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.semakmule as semakmule_module

    monkeypatch.setattr(semakmule_module, "get_semakmule_client", lambda: _FakeSemakMule())

    # Anonymous lookup of a not-yet-registered MY account still returns the gov signal.
    resp = await client.get(
        "/api/v1/entities/account", params={"country": "MY", "bank": "MBB", "account": "123123123"}
    )
    body = resp.json()
    assert body["data"]["gov_check"]["found"] is True
    assert body["data"]["gov_check"]["source"] == "semakmule.rmp.gov.my"


async def test_my_ewallet_lookup_uses_phone_checker(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E-wallets are phone-based → the *telefon* checker is selected."""
    import app.services.semakmule as semakmule_module

    fake = _FakeSemakMule()
    monkeypatch.setattr(semakmule_module, "get_semakmule_client", lambda: fake)

    resp = await client.get(
        "/api/v1/entities/account",
        params={"country": "MY", "bank": "TNGS", "account": "601234567890"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["gov_check"]["category"] == "phone"
    assert fake.last_category == "phone"


async def test_my_report_persists_gov_flag(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.semakmule as semakmule_module

    monkeypatch.setattr(semakmule_module, "get_semakmule_client", lambda: _FakeSemakMule())

    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "myscanner@trustpay.dev", "password": "s3cure-Passw0rd"},
    )
    token = signup.json()["access_token"]
    account = "555000111"

    created = await client.post(
        "/api/v1/reports",
        json={
            "target": {"kind": "ACCOUNT", "country": "MY", "bank": "MBB", "account": account},
            "category": "ONLINE_SHOP_GHOSTING",
            "severity": 4,
            "description": "Malaysian mule account reported through the app.",
            "consent": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 202, created.text

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import PaymentEntity

    async with SessionLocal() as db:
        entity = await db.scalar(
            select(PaymentEntity).where(PaymentEntity.account_masked == "555-****-111")
        )
    assert entity.is_gov_blacklisted is True
    assert entity.gov_source == "semakmule.rmp.gov.my"
    assert entity.risk_score == 100


async def test_admin_semakmule_check(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.semakmule as semakmule_module

    monkeypatch.setattr(semakmule_module, "get_semakmule_client", lambda: _FakeSemakMule())

    signup = await client.post(
        "/api/v1/auth/signup", json={"email": "myadmin@trustpay.dev", "password": "s3cure-Passw0rd"}
    )
    token = signup.json()["access_token"]
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.enums import Role
    from app.models import User

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "myadmin@trustpay.dev"))
        user.role = Role.ANALYST.value
        await db.commit()

    resp = await client.post(
        "/api/v1/admin/gov/semakmule/check",
        json={"bank": "MBB", "account": "999888777"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["found"] is True
