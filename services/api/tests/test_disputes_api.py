"""Owner claim, dispute & safe-harbor tests (Phase 5)."""

import uuid

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import get_settings
from app.core import audit
from app.db import SessionLocal
from app.enums import ReportStatus, Role, UserStatus
from app.models import FraudReport, OwnerDispute, PaymentEntity, User
from app.services.dispute_service import apply_dispute_cap

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


async def _make_admin(email: str) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        user.role = Role.ANALYST.value
        await db.commit()


async def _entity_for(client: httpx.AsyncClient, reporter: str, account: str) -> tuple[str, str]:
    body = {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Seller took my payment and vanished without shipping anything.",
        "consent": True,
    }
    created = await client.post("/api/v1/reports", json=body, headers=_auth(reporter))
    report_id = created.json()["data"]["report_id"]
    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": account}
    )
    return lookup.json()["data"]["entity"]["id"], report_id


def test_apply_dispute_cap_is_rise_only() -> None:
    high = PaymentEntity(is_under_dispute=True, risk_score=88, dispute_hold_score_cap=45)
    assert apply_dispute_cap(high, 95) == 88  # never pulls a high score down

    low = PaymentEntity(is_under_dispute=True, risk_score=15, dispute_hold_score_cap=45)
    assert apply_dispute_cap(low, 70) == 45  # caps a new rise

    normal = PaymentEntity(is_under_dispute=False, risk_score=10, dispute_hold_score_cap=45)
    assert apply_dispute_cap(normal, 90) == 90


async def test_claim_passbook_engages_safe_harbor(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "claim-reporter@trustpay.dev")
    owner = await _signup(client, "claim-owner@trustpay.dev")
    entity_id, _ = await _entity_for(client, reporter, "8500000001")

    claim = await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/passbook.jpg"},
        headers=_auth(owner),
    )
    assert claim.status_code == 202, claim.text
    assert claim.json()["data"]["claim_stage"] == "UNDER_REVIEW"
    assert "OTP" in claim.json()["data"]["note"]

    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "8500000001"}
    )
    risk = lookup.json()["data"]["risk_assessment"]
    assert risk["is_under_dispute"] is True
    assert risk["is_verified_legit"] is True

    # A different owner cannot claim the same entity.
    intruder = await _signup(client, "claim-intruder@trustpay.dev")
    conflict = await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/x.jpg"},
        headers=_auth(intruder),
    )
    assert conflict.status_code == 409


async def test_nmid_mismatch_rejects_identity(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "nmid-reporter@trustpay.dev")
    owner = await _signup(client, "nmid-owner@trustpay.dev")
    entity_id, _ = await _entity_for(client, reporter, "8500000002")

    claim = await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={
            "proof_type": "MERCHANT_PORTAL_NMID",
            "proof_document_url": "s3://q/nmid.png",
            "declared_reference": "999999999999999999",
        },
        headers=_auth(owner),
    )
    assert claim.json()["data"]["claim_stage"] == "REJECTED_IDENTITY"


async def test_micro_deposit_verification(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "dep-reporter@trustpay.dev")
    owner = await _signup(client, "dep-owner@trustpay.dev")
    entity_id, _ = await _entity_for(client, reporter, "8500000003")

    claim = await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "MICRO_DEPOSIT_OTP", "proof_document_url": "pending"},
        headers=_auth(owner),
    )
    assert claim.json()["data"]["claim_stage"] == "SUBMITTED"

    start = await client.post(
        f"/api/v1/entities/{entity_id}/claim/micro-deposit/start", headers=_auth(owner)
    )
    code = start.json()["data"]["dev_code"]

    bad = await client.post(
        f"/api/v1/entities/{entity_id}/claim/micro-deposit/verify",
        json={"code": "000000"},
        headers=_auth(owner),
    )
    assert bad.json()["data"]["claim_stage"] == "REJECTED_IDENTITY"

    good = await client.post(
        f"/api/v1/entities/{entity_id}/claim/micro-deposit/verify",
        json={"code": code},
        headers=_auth(owner),
    )
    assert good.json()["data"]["claim_stage"] == "UNDER_REVIEW"


async def _latest_pending_approval(client: httpx.AsyncClient, admin_token: str) -> str:
    """ADR-021: destructive decisions queue an approval — return its id."""
    resp = await client.get(
        "/api/v1/admin/approvals", params={"status_filter": "PENDING"}, headers=_auth(admin_token)
    )
    approvals = resp.json()["data"]["approvals"]
    assert approvals, "expected a pending four-eyes approval"
    return approvals[-1]["id"]


async def test_dispute_and_admin_resolution_removes_review(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "dis-reporter@trustpay.dev")
    owner = await _signup(client, "dis-owner@trustpay.dev")
    admin = await _signup(client, "dis-admin@trustpay.dev")
    second = await _signup(client, "dis-admin2@trustpay.dev")
    await _make_admin("dis-admin@trustpay.dev")
    await _make_admin("dis-admin2@trustpay.dev")
    entity_id, report_id = await _entity_for(client, reporter, "8500000004")

    await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "MBANKING_SCREENSHOT", "proof_document_url": "s3://q/m.jpg"},
        headers=_auth(owner),
    )
    dispute = await client.post(
        f"/api/v1/entities/{entity_id}/disputes",
        json={
            "reason": "FALSE_CLAIM",
            "justification": "This account is mine and the claim is false.",
        },
        headers=_auth(owner),
    )
    assert dispute.status_code == 201
    dispute_id = dispute.json()["data"]["id"]

    mine = await client.get("/api/v1/disputes/me", headers=_auth(owner))
    assert len(mine.json()["data"]["disputes"]) == 1

    requested = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        json={"decision": "APPROVED_REMOVED", "notes": "Ownership confirmed"},
        headers=_auth(admin),
    )
    # ADR-021: request only — dispute stays UNDER_REVIEW until a 2nd admin approves
    assert requested.json()["data"]["status"] in ("UNDER_REVIEW", "SUBMITTED")
    approval_id = await _latest_pending_approval(client, admin)

    same_admin = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(admin)
    )
    assert same_admin.status_code == 409  # four-eyes: requester cannot approve

    done = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(second)
    )
    assert done.json()["data"]["status"] == "APPROVED"

    async with SessionLocal() as db:
        report = await db.get(FraudReport, uuid.UUID(report_id))
        entity = await db.get(PaymentEntity, uuid.UUID(entity_id))
        dispute_row = await db.get(OwnerDispute, uuid.UUID(dispute_id))
        reporter_user = await db.scalar(
            select(User).where(User.email == "dis-reporter@trustpay.dev")
        )
        chain_ok = await audit.verify_chain(db)
    assert report.status == ReportStatus.REMOVED_BY_DISPUTE
    assert dispute_row.status == "APPROVED_REMOVED"
    assert entity.is_under_dispute is False
    assert reporter_user.status == UserStatus.WARNED
    assert chain_ok is True


async def test_rejected_upheld_clears_freeze(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "up-reporter@trustpay.dev")
    owner = await _signup(client, "up-owner@trustpay.dev")
    admin = await _signup(client, "up-admin@trustpay.dev")
    await _make_admin("up-admin@trustpay.dev")
    entity_id, report_id = await _entity_for(client, reporter, "8500000005")

    await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/p.jpg"},
        headers=_auth(owner),
    )
    dispute = await client.post(
        f"/api/v1/entities/{entity_id}/disputes",
        json={"reason": "OTHER", "justification": "There is a misunderstanding here."},
        headers=_auth(owner),
    )
    dispute_id = dispute.json()["data"]["id"]

    await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        json={"decision": "REJECTED_UPHELD"},
        headers=_auth(admin),
    )
    async with SessionLocal() as db:
        entity = await db.get(PaymentEntity, uuid.UUID(entity_id))
        report = await db.get(FraudReport, uuid.UUID(report_id))
    assert entity.is_under_dispute is False
    assert report.status == ReportStatus.ACTIVE


async def test_settlement_marks_report(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "set-reporter@trustpay.dev")
    owner = await _signup(client, "set-owner@trustpay.dev")
    admin = await _signup(client, "set-admin@trustpay.dev")
    second = await _signup(client, "set-admin2@trustpay.dev")
    await _make_admin("set-admin@trustpay.dev")
    await _make_admin("set-admin2@trustpay.dev")
    entity_id, report_id = await _entity_for(client, reporter, "8500000006")

    await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/p.jpg"},
        headers=_auth(owner),
    )
    dispute = await client.post(
        f"/api/v1/entities/{entity_id}/disputes",
        json={"reason": "RESOLVED_REFUNDED", "justification": "We refunded the buyer already."},
        headers=_auth(owner),
    )
    dispute_id = dispute.json()["data"]["id"]
    await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        json={"decision": "SETTLEMENT"},
        headers=_auth(admin),
    )
    # ADR-021: settlement is trust-altering → queued for a second admin
    approval_id = await _latest_pending_approval(client, admin)
    done = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(second)
    )
    assert done.json()["data"]["status"] == "APPROVED"
    async with SessionLocal() as db:
        report = await db.get(FraudReport, uuid.UUID(report_id))
    assert report.status == ReportStatus.RESOLVED_BY_SETTLEMENT


async def test_owner_response_requires_verified_owner(client: httpx.AsyncClient) -> None:
    reporter = await _signup(client, "resp-reporter@trustpay.dev")
    owner = await _signup(client, "resp-owner@trustpay.dev")
    entity_id, _ = await _entity_for(client, reporter, "8500000007")

    await client.post(
        f"/api/v1/entities/{entity_id}/claim",
        json={"proof_type": "BANK_PASSBOOK", "proof_document_url": "s3://q/p.jpg"},
        headers=_auth(owner),
    )
    ok = await client.patch(
        f"/api/v1/entities/{entity_id}/owner-response",
        json={"response": "We are a legitimate business; this was a chargeback dispute."},
        headers=_auth(owner),
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["owner_response"].startswith("We are a legitimate")

    lookup = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "8500000007"}
    )
    assert lookup.json()["data"]["entity"]["owner_response"]
