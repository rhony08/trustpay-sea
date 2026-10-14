"""Community moderation tests (Phase 4): votes, flags, admin resolution, audit."""

import uuid

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import func, select

from app.config import get_settings
from app.core import audit
from app.db import SessionLocal
from app.enums import ReportStatus, Role, UserStatus
from app.models import AuditLog, FraudReport, User

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


async def _make_admin(email: str) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        user.role = Role.ANALYST.value
        await db.commit()


async def _report(client: httpx.AsyncClient, token: str, account: str) -> str:
    body = {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Seller took payment and vanished without shipping anything.",
        "consent": True,
    }
    resp = await client.post("/api/v1/reports", json=body, headers=_auth(token))
    assert resp.status_code == 202, resp.text
    return resp.json()["data"]["report_id"]


async def test_votes_are_idempotent_and_counted(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "vote-reporter@trustpay.dev")
    voter = await _signup(client, "vote-voter@trustpay.dev")
    report_id = await _report(client, reporter, "8100000001")

    first = await client.post(
        f"/api/v1/reports/{report_id}/vote", json={"vote": 1}, headers=_auth(voter)
    )
    assert first.json()["data"]["upvotes"] == 1

    # Same user voting again must not double-count.
    again = await client.post(
        f"/api/v1/reports/{report_id}/vote", json={"vote": 1}, headers=_auth(voter)
    )
    assert again.json()["data"]["upvotes"] == 1

    # Change vote direction.
    flipped = await client.post(
        f"/api/v1/reports/{report_id}/vote", json={"vote": -1}, headers=_auth(voter)
    )
    assert flipped.json()["data"] == {"upvotes": 0, "downvotes": 1}

    removed = await client.delete(f"/api/v1/reports/{report_id}/vote", headers=_auth(voter))
    assert removed.json()["data"] == {"upvotes": 0, "downvotes": 0}


async def test_flag_dedupe_per_reason(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "flag-reporter@trustpay.dev")
    flagger = await _signup(client, "flag-flagger@trustpay.dev")
    report_id = await _report(client, reporter, "8100000002")

    first = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "DEFAMATION_SPAM"},
        headers=_auth(flagger),
    )
    assert first.status_code == 201

    dup = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "DEFAMATION_SPAM"},
        headers=_auth(flagger),
    )
    assert dup.status_code == 409

    other = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "INCORRECT_ACCOUNT"},
        headers=_auth(flagger),
    )
    assert other.status_code == 201

    mine = await client.get("/api/v1/flags/me", headers=_auth(flagger))
    assert len(mine.json()["data"]["flags"]) == 2


async def test_admin_queue_requires_role(client: httpx.AsyncClient) -> None:
    user = await _signup(client, "not-admin@trustpay.dev")
    assert (await client.get("/api/v1/admin/flags", headers=_auth(user))).status_code == 403

    await _make_admin("not-admin@trustpay.dev")
    assert (await client.get("/api/v1/admin/flags", headers=_auth(user))).status_code == 200


async def test_upheld_flag_hides_report_and_warns_reporter(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "upheld-reporter@trustpay.dev")
    flagger = await _signup(client, "upheld-flagger@trustpay.dev")
    admin = await _signup(client, "upheld-admin@trustpay.dev")
    await _make_admin("upheld-admin@trustpay.dev")

    report_id = await _report(client, reporter, "8100000003")
    flag = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "DEFAMATION_SPAM", "details": "Smear"},
        headers=_auth(flagger),
    )
    flag_id = flag.json()["data"]["id"]

    resolved = await client.post(
        f"/api/v1/admin/flags/{flag_id}/resolve",
        json={"decision": "UPHELD", "notes": "Confirmed spam"},
        headers=_auth(admin),
    )
    assert resolved.json()["data"]["status"] == "UPHELD"

    async with SessionLocal() as db:
        report = await db.get(FraudReport, uuid.UUID(report_id))
        reporter_user = await db.scalar(
            select(User).where(User.email == "upheld-reporter@trustpay.dev")
        )
        audit_count = await db.scalar(select(func.count(AuditLog.id)))
        chain_ok = await audit.verify_chain(db)
    assert report.status == ReportStatus.HIDDEN
    assert reporter_user.status == UserStatus.WARNED
    assert audit_count >= 1
    assert chain_ok is True


async def test_dismissed_flag_keeps_report_visible(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "dismiss-reporter@trustpay.dev")
    flagger = await _signup(client, "dismiss-flagger@trustpay.dev")
    admin = await _signup(client, "dismiss-admin@trustpay.dev")
    await _make_admin("dismiss-admin@trustpay.dev")

    report_id = await _report(client, reporter, "8100000004")
    flag = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "OFFENSIVE_CONTENT"},
        headers=_auth(flagger),
    )
    flag_id = flag.json()["data"]["id"]

    await client.post(
        f"/api/v1/admin/flags/{flag_id}/resolve",
        json={"decision": "DISMISSED"},
        headers=_auth(admin),
    )
    async with SessionLocal() as db:
        report = await db.get(FraudReport, uuid.UUID(report_id))
    assert report.status == ReportStatus.ACTIVE


async def test_bad_faith_flagger_gets_warned(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "bf-reporter@trustpay.dev")
    flagger = await _signup(client, "bf-flagger@trustpay.dev")
    admin = await _signup(client, "bf-admin@trustpay.dev")
    await _make_admin("bf-admin@trustpay.dev")

    for i in range(5):
        report_id = await _report(client, reporter, f"820000{i:04d}")
        flag = await client.post(
            f"/api/v1/reports/{report_id}/flags",
            json={"reason": "DEFAMATION_SPAM"},
            headers=_auth(flagger),
        )
        flag_id = flag.json()["data"]["id"]
        await client.post(
            f"/api/v1/admin/flags/{flag_id}/resolve",
            json={"decision": "DISMISSED"},
            headers=_auth(admin),
        )

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "bf-flagger@trustpay.dev"))
    assert user.status == UserStatus.WARNED


async def test_admin_flag_queue_enriched_and_report_detail(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "aq-reporter@trustpay.dev")
    flagger = await _signup(client, "aq-flagger@trustpay.dev")
    admin = await _signup(client, "aq-admin@trustpay.dev")
    await _make_admin("aq-admin@trustpay.dev")

    report_id = await _report(client, reporter, "8100000009")
    await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "DEFAMATION_SPAM", "details": "looks fake"},
        headers=_auth(flagger),
    )

    queue = (await client.get("/api/v1/admin/flags", headers=_auth(admin))).json()["data"]["flags"]
    assert queue
    entry = next(f for f in queue if f["report"] and f["report"]["id"] == report_id)
    assert entry["entity"]["account_masked"]
    assert entry["report"]["category"]

    detail = (await client.get(f"/api/v1/admin/reports/{report_id}", headers=_auth(admin))).json()[
        "data"
    ]
    assert detail["entity"]["account_masked"]
    assert "evidence" in detail and "ai_forensic_notes" in detail


async def test_banned_reporter_cannot_submit(client: httpx.AsyncClient) -> None:
    token = await _signup(client, "banned@trustpay.dev")
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "banned@trustpay.dev"))
        user.status = UserStatus.BANNED
        await db.commit()

    body = {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": "8300000001"},
        "category": "OTHER",
        "severity": 2,
        "description": "This account scammed me and I want it recorded for others.",
        "consent": True,
    }
    resp = await client.post("/api/v1/reports", json=body, headers=_auth(token))
    assert resp.status_code == 403
