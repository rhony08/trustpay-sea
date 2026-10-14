"""Risk scorer, anti-brigading, gov adapter & admin portal tests (Phase 6)."""

import uuid

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import (
    AdminVerificationStatus,
    EntityType,
    ProcessingStatus,
    ReportStatus,
    Role,
    Scheme,
)
from app.models import FraudReport, PaymentEntity, User
from app.services import admin_service, gov_adapter
from app.services.anti_brigading import detect_anomaly
from app.services.entity_service import upsert_entity
from app.services.risk_scorer import recompute_entity_score

PASSWORD = "s3cure-Passw0rd"


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    gov_adapter.clear_mock_feed()
    await redis.aclose()


async def _signup(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _set_role(email: str, role: Role) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        user.role = role.value
        await db.commit()


async def _new_entity() -> uuid.UUID:
    async with SessionLocal() as db:
        entity = await upsert_entity(
            db,
            entity_type=EntityType.BANK_ACCOUNT,
            scheme=Scheme.BANK,
            country_code="ID",
            institution_code="014",
            account_hash=uuid.uuid4().hex,
            account_masked="999-****-999",
        )
    return entity.id


async def _add_report(
    entity_id: uuid.UUID,
    *,
    severity: int = 3,
    admin_approved: bool = False,
    settled: bool = False,
    reporter_id: uuid.UUID | None = None,
    tampering: bool = False,
) -> None:
    async with SessionLocal() as db:
        db.add(
            FraudReport(
                payment_entity_id=entity_id,
                reporter_user_id=reporter_id,
                category="ONLINE_SHOP_GHOSTING",
                severity=severity,
                description="test report for scoring",
                processing_status=ProcessingStatus.PUBLISHED,
                admin_verification_status=(
                    AdminVerificationStatus.APPROVED
                    if admin_approved
                    else AdminVerificationStatus.PENDING
                ),
                status=ReportStatus.RESOLVED_BY_SETTLEMENT if settled else ReportStatus.ACTIVE,
                ai_forensic_notes={"tampering_detected": tampering} if tampering else None,
            )
        )
        await db.commit()


async def test_scorer_breakdown_and_factors() -> None:
    entity_id = await _new_entity()
    await _add_report(entity_id, severity=3, admin_approved=True)
    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, entity_id)
        result = await recompute_entity_score(db, entity)
    labels = {f["label"]: f["weight"] for f in result.factors}
    assert labels["admin_verified"] == 35
    assert labels["community"] == 30  # 10 * severity 3
    assert result.score == 15 + 35 + 30


async def test_scorer_merchant_kyc_and_settlement_discounts() -> None:
    entity_id = await _new_entity()
    await _add_report(entity_id, severity=2)
    await _add_report(entity_id, severity=1, settled=True)
    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, entity_id)
        entity.is_owner_verified = True
        await db.commit()
        result = await recompute_entity_score(db, entity)
    labels = {f["label"]: f["weight"] for f in result.factors}
    assert labels["merchant_kyc"] == -20
    assert labels["resolution"] == -15


async def test_anti_brigading_burst_detected() -> None:
    entity_id = await _new_entity()
    # Three distinct low-trust reporters within the 3h window.
    for i in range(3):
        uid = uuid.uuid4()
        async with SessionLocal() as db:
            db.add(User(email=f"brig{i}-{uid}@x.dev", password_hash="x", identity_trust=10))
            await db.commit()
            user = await db.scalar(select(User).where(User.email == f"brig{i}-{uid}@x.dev"))
        await _add_report(entity_id, reporter_id=user.id)
    async with SessionLocal() as db:
        spike, dampen = await detect_anomaly(db, entity_id)
    assert spike is True
    assert dampen == 0.45


async def test_gov_feed_forces_score_100() -> None:
    entity_id = await _new_entity()
    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, entity_id)
        gov_adapter.add_mock_entry(entity.account_hash, "cekrekening.id")
        applied = await admin_service.sync_gov_feed(db)
        entity = await db.get(PaymentEntity, entity_id)
    assert applied == 1
    assert entity.is_gov_blacklisted is True
    assert entity.gov_source == "cekrekening.id"
    assert entity.risk_score == 100


async def test_admin_dashboard_and_audit_chain(client: httpx.AsyncClient) -> None:
    admin = await _signup(client, "dash-admin@trustpay.dev")
    await _set_role("dash-admin@trustpay.dev", Role.ANALYST)

    dash = await client.get("/api/v1/admin/dashboard", headers=_auth(admin))
    assert dash.status_code == 200
    assert "pending_flags" in dash.json()["data"]

    audit = await client.get("/api/v1/admin/audit", headers=_auth(admin))
    assert audit.json()["data"]["chain_ok"] is True


async def test_dual_control_requires_second_admin(client: httpx.AsyncClient) -> None:
    first = await _signup(client, "approver-a@trustpay.dev")
    second = await _signup(client, "approver-b@trustpay.dev")
    await _set_role("approver-a@trustpay.dev", Role.ANALYST)
    await _set_role("approver-b@trustpay.dev", Role.ANALYST)
    entity_id = await _new_entity()

    created = await client.post(
        "/api/v1/admin/approvals",
        json={
            "action": "gov_override",
            "subject_type": "payment_entity",
            "subject_id": str(entity_id),
            "payload": {"source": "cekrekening.id"},
        },
        headers=_auth(first),
    )
    approval_id = created.json()["data"]["id"]

    # Same admin cannot approve their own request.
    same = await client.post(f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(first))
    assert same.status_code == 409

    ok = await client.post(f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(second))
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "APPROVED"

    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, entity_id)
    assert entity.is_gov_blacklisted is True
    assert entity.risk_score == 100
