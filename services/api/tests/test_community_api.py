"""Community/engagement tests (Phase 3B): trust, verify, watchlist, badges, receipts."""

import uuid

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import BadgeType, EntityVerificationStatus
from app.models import PaymentEntity, User, UserNotification
from app.services import reputation
from app.workers import report_pipeline

PASSWORD = "s3cure-Passw0rd"


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    await redis.aclose()


async def _signup(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _report(client: httpx.AsyncClient, token: str, account: str) -> str:
    body = {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Seller took my payment and then disappeared entirely.",
        "consent": True,
    }
    resp = await client.post("/api/v1/reports", json=body, headers=_auth(token))
    assert resp.status_code == 202, resp.text
    return resp.json()["data"]["report_id"]


async def _publish(report_id: str) -> None:
    async with SessionLocal() as db:
        await report_pipeline.process_report(db, uuid.UUID(report_id))


async def test_profile_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/profile/me")).status_code == 401


async def test_profile_trust_tier(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "tier@trustpay.dev")
    resp = await client.get("/api/v1/profile/me", headers=_auth(token))
    data = resp.json()["data"]
    assert data["tier"] == "CONTRIBUTOR"  # reputation 50
    assert data["badges"] == []


async def test_phone_verification_flow(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "verify@trustpay.dev")
    start = await client.post(
        "/api/v1/profile/verify/phone/start",
        json={"phone": "+6281234567890"},
        headers=_auth(token),
    )
    code = start.json()["data"]["dev_code"]

    bad = await client.post(
        "/api/v1/profile/verify/phone/confirm", json={"code": "000000"}, headers=_auth(token)
    )
    assert bad.status_code == 400

    ok = await client.post(
        "/api/v1/profile/verify/phone/confirm", json={"code": code}, headers=_auth(token)
    )
    data = ok.json()["data"]
    assert data["phone_verified"] is True
    assert data["identity_trust"] == 40  # 10 + 30
    assert any(b["badge"] == BadgeType.VERIFIED_REPORTER.value for b in data["badges"])


async def test_watchlist_add_list_remove(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "watch-reporter@trustpay.dev")
    watcher = await _signup(client, "watch-watcher@trustpay.dev")
    account = "8000001001"
    await _report(client, reporter, account)

    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": account}
    )
    entity_id = lookup.json()["data"]["entity"]["id"]

    created = await client.post(
        "/api/v1/profile/watchlist", json={"entity_id": entity_id}, headers=_auth(watcher)
    )
    assert created.status_code == 201

    listing = await client.get("/api/v1/profile/watchlist", headers=_auth(watcher))
    assert listing.json()["data"]["watchlist"][0]["entity_id"] == entity_id

    removed = await client.delete(f"/api/v1/profile/watchlist/{entity_id}", headers=_auth(watcher))
    assert removed.status_code == 204
    assert (await client.get("/api/v1/profile/watchlist", headers=_auth(watcher))).json()["data"][
        "watchlist"
    ] == []


async def test_watchers_notified_on_publish(client: httpx.AsyncClient) -> None:
    watcher = await _signup(client, "watcher-notify@trustpay.dev")
    reporter = await _signup(client, "reporter-notify@trustpay.dev")
    account = "8000002002"

    # Report first so the entity exists, then watch it.
    await _report(client, reporter, account)
    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": account}
    )
    entity_id = uuid.UUID(lookup.json()["data"]["entity"]["id"])
    await client.post(
        "/api/v1/profile/watchlist", json={"entity_id": str(entity_id)}, headers=_auth(watcher)
    )

    # A second reporter files a report → publish → watcher notified.
    report_id = await _report(client, reporter, account)
    await _publish(report_id)

    async with SessionLocal() as db:
        watcher_user = await db.scalar(
            select(User).where(User.email == "watcher-notify@trustpay.dev")
        )
        count = await db.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == watcher_user.id,
                UserNotification.type == "WATCHED_ENTITY_REPORT",
            )
        )
    assert count >= 1


async def test_scam_quiz_grants_badge(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "quiz@trustpay.dev")
    questions = (await client.get("/api/v1/quiz")).json()["data"]["questions"]
    assert len(questions) == 3
    # answers: q1=1, q2=2, q3=1 (all correct)
    resp = await client.post(
        "/api/v1/profile/quiz/submit", json={"answers": [1, 2, 1]}, headers=_auth(token)
    )
    data = resp.json()["data"]
    assert data["passed"] is True
    badges = (await client.get("/api/v1/profile/badges", headers=_auth(token))).json()["data"][
        "badges"
    ]
    assert any(b["badge"] == BadgeType.ANTI_SCAM_AWARE.value for b in badges)


async def test_pioneer_badge_on_verification(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "pioneer@trustpay.dev")
    account = "8000003003"
    await _report(client, reporter, account)
    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": account}
    )
    entity_id = uuid.UUID(lookup.json()["data"]["entity"]["id"])

    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, entity_id)
        await reputation.set_entity_verification(
            db, entity, EntityVerificationStatus.ADMIN_CONFIRMED_FRAUD
        )
        user = await db.scalar(select(User).where(User.email == "pioneer@trustpay.dev"))
        badges = await reputation.list_badges(db, user.id)
    assert any(
        b.badge == BadgeType.PIONEER_WARN.value and b.scope == str(entity_id) for b in badges
    )


async def test_playbook_endpoints(client: httpx.AsyncClient) -> None:
    listing = (await client.get("/api/v1/playbook")).json()["data"]["playbooks"]
    assert len(listing) >= 9
    entry = await client.get("/api/v1/playbook/PHISHING_PRETEXTING")
    assert entry.json()["data"]["title"].startswith("Phishing")
    assert (await client.get("/api/v1/playbook/NOPE")).status_code == 404


async def test_diligence_receipt_roundtrip(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "receipt@trustpay.dev")
    account = "8000004004"
    report_id = await _report(client, reporter, account)
    await _publish(report_id)

    created = await client.post(
        "/api/v1/receipts/account", params={"country": "ID", "bank": "014", "account": account}
    )
    assert created.status_code == 200, created.text
    token = created.json()["data"]["token"]

    verified = await client.get(f"/api/v1/receipts/{token}")
    assert verified.status_code == 200
    assert verified.json()["data"]["account_masked"].startswith("800")
    assert verified.json()["data"]["risk_level"]

    tampered = await client.get(f"/api/v1/receipts/{token[:-1]}0")
    assert tampered.status_code == 400


async def test_receipt_unknown_entity_404(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/receipts/account",
        params={"country": "ID", "bank": "014", "account": "8099999999"},
    )
    assert resp.status_code == 404
