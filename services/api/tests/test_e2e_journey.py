"""End-to-end journey smoke (Phase 7.2, backend): the full user story in one test.

search → report + evidence → publish → vote → flag → admin resolve → claim →
dispute → admin settle. Mirrors the demo script; rolls up the whole stack.
"""

import uuid
from pathlib import Path

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import ReportStatus, Role, UserStatus
from app.models import FraudReport, User
from app.workers import report_pipeline

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
PNG = (VECTORS / "qris_static.png").read_bytes()
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


async def test_full_user_journey(client: httpx.AsyncClient) -> None:
    account = "8600012345"
    reporter = await _signup(client, "journey-reporter@trustpay.dev")
    voter = await _signup(client, "journey-voter@trustpay.dev")
    owner = await _signup(client, "journey-owner@trustpay.dev")
    admin = await _signup(client, "journey-admin@trustpay.dev")
    second_admin = await _signup(client, "journey-admin2@trustpay.dev")

    async with SessionLocal() as db:
        for email in ("journey-admin@trustpay.dev", "journey-admin2@trustpay.dev"):
            user = await db.scalar(select(User).where(User.email == email))
            user.role = Role.ANALYST.value
        await db.commit()

    # 1. Report + evidence
    created = await client.post(
        "/api/v1/reports",
        json={
            "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
            "category": "ONLINE_SHOP_GHOSTING",
            "severity": 4,
            "description": "Paid for a phone that never shipped; seller blocked me.",
            "consent": True,
        },
        headers=_auth(reporter),
    )
    report_id = created.json()["data"]["report_id"]
    await client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("slip.png", PNG, "image/png")},
        headers=_auth(reporter),
    )

    # 2. Async worker publishes
    async with SessionLocal() as db:
        assert await report_pipeline.process_report(db, uuid.UUID(report_id)) == "published"

    # 3. Lookup shows the published report + a score breakdown
    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": account}
    )
    data = lookup.json()["data"]
    entity_id = data["entity"]["id"]
    assert any(r["id"] == report_id for r in data["reports"])
    assert data["risk_assessment"]["factors"]

    # 4. Vote + flag
    await client.post(f"/api/v1/reports/{report_id}/vote", json={"vote": 1}, headers=_auth(voter))
    flag = await client.post(
        f"/api/v1/reports/{report_id}/flags",
        json={"reason": "DEFAMATION_SPAM"},
        headers=_auth(voter),
    )
    flag_id = flag.json()["data"]["id"]

    # 5. Admin upholds the flag → ADR-021 queues hide_report; 2nd admin approves
    await client.post(
        f"/api/v1/admin/flags/{flag_id}/resolve",
        json={"decision": "UPHELD"},
        headers=_auth(admin),
    )
    approvals = await client.get(
        "/api/v1/admin/approvals", params={"status_filter": "PENDING"}, headers=_auth(admin)
    )
    hide = [a for a in approvals.json()["data"]["approvals"] if a["action"] == "hide_report"]
    assert hide, "expected pending hide_report approval"
    done = await client.post(
        f"/api/v1/admin/approvals/{hide[-1]['id']}/approve", headers=_auth(second_admin)
    )
    assert done.json()["data"]["status"] == "APPROVED"
    async with SessionLocal() as db:
        report = await db.get(FraudReport, uuid.UUID(report_id))
        reporter_user = await db.scalar(
            select(User).where(User.email == "journey-reporter@trustpay.dev")
        )
    assert report.status == ReportStatus.HIDDEN
    assert reporter_user.status == UserStatus.WARNED

    # 6. Owner claims → disputes → admin settles
    claim = await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/p.jpg"},
        headers=_auth(owner),
    )
    assert claim.json()["data"]["claim_stage"] == "UNDER_REVIEW"
    dispute = await client.post(
        f"/api/v1/entities/{entity_id}/disputes",
        json={"reason": "FALSE_CLAIM", "justification": "This is our legitimate business account."},
        headers=_auth(owner),
    )
    dispute_id = dispute.json()["data"]["id"]
    requested = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        json={"decision": "SETTLEMENT", "notes": "Refund issued"},
        headers=_auth(admin),
    )
    # ADR-021: settlement queues for a second admin
    assert requested.json()["data"]["status"] in ("UNDER_REVIEW", "SUBMITTED")
    approvals = await client.get(
        "/api/v1/admin/approvals", params={"status_filter": "PENDING"}, headers=_auth(admin)
    )
    settle = [a for a in approvals.json()["data"]["approvals"] if a["action"] == "settlement"]
    assert settle, "expected pending settlement approval"
    done = await client.post(
        f"/api/v1/admin/approvals/{settle[-1]['id']}/approve", headers=_auth(second_admin)
    )
    assert done.json()["data"]["status"] == "APPROVED"
    async with SessionLocal() as db:
        from app.models import OwnerDispute

        dispute_row = await db.get(OwnerDispute, uuid.UUID(dispute_id))
    assert dispute_row.status == "SETTLEMENT"

    # 7. Admin dashboard + audit remain consistent
    dash = await client.get("/api/v1/admin/dashboard", headers=_auth(admin))
    assert dash.status_code == 200
    audit = await client.get("/api/v1/admin/audit", headers=_auth(admin))
    assert audit.json()["data"]["chain_ok"] is True
