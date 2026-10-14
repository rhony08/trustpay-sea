"""Report submission / evidence / status / feed integration tests (Phase 2)."""

import uuid
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
import redis.asyncio as aioredis
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import FraudReport
from app.workers import report_pipeline

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
PNG = (VECTORS / "qris_static.png").read_bytes()

PASSWORD = "s3cure-Passw0rd"


def _synthetic_png(seed: int) -> bytes:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:] = (seed % 200, (seed * 2) % 200, (seed * 3) % 200)
    image[8:24, 8:24] = 255
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


@pytest.fixture(autouse=True)
async def _flush_rate_limit() -> None:
    redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    async for key in redis.scan_iter("rl:*"):
        await redis.delete(key)
    await redis.aclose()


async def _token(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "display_name": "Reporter"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _payload(account: str, **overrides) -> dict:
    body = {
        "target": {
            "kind": "ACCOUNT",
            "country": "ID",
            "bank": "014",
            "account": account,
        },
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Seller on Instagram took payment and then ghosted me for weeks.",
        "currency": "IDR",
        "loss_amount": 1500000,
        "consent": True,
    }
    body.update(overrides)
    return body


async def test_report_requires_auth(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/reports", json=_payload("8830192831"))
    assert resp.status_code == 401


async def test_report_requires_consent(client: httpx.AsyncClient) -> None:
    token = await _token(client, "consent@trustpay.dev")
    resp = await client.post(
        "/api/v1/reports", json=_payload("8880001111", consent=False), headers=_auth(token)
    )
    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"]


async def test_report_unsupported_bank_400(client: httpx.AsyncClient) -> None:
    token = await _token(client, "badbank@trustpay.dev")
    body = _payload("8830192831")
    body["target"]["bank"] = "999"
    resp = await client.post("/api/v1/reports", json=body, headers=_auth(token))
    assert resp.status_code == 400


async def test_report_idempotency(client: httpx.AsyncClient) -> None:
    token = await _token(client, "idem@trustpay.dev")
    headers = {**_auth(token), "Idempotency-Key": "abc-123"}
    description = "Idempotent submission must create exactly one unique report."
    body = _payload("8770001234", description=description)
    first = await client.post("/api/v1/reports", json=body, headers=headers)
    second = await client.post("/api/v1/reports", json=body, headers=headers)
    assert first.status_code == 202
    assert first.json()["data"]["report_id"] == second.json()["data"]["report_id"]

    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count(FraudReport.id)).where(FraudReport.description == description)
        )
    assert count == 1


async def test_report_entity_hourly_quota(client: httpx.AsyncClient) -> None:
    token = await _token(client, "quota@trustpay.dev")
    account = "8660005555"
    statuses = []
    for _ in range(6):
        resp = await client.post("/api/v1/reports", json=_payload(account), headers=_auth(token))
        statuses.append(resp.status_code)
    assert statuses[:5] == [202] * 5
    assert statuses[5] == 429


async def test_full_report_lifecycle_and_feed(client: httpx.AsyncClient) -> None:
    token = await _token(client, "lifecycle@trustpay.dev")
    account = "8550009876"

    created = await client.post("/api/v1/reports", json=_payload(account), headers=_auth(token))
    assert created.status_code == 202
    report_id = created.json()["data"]["report_id"]
    assert created.json()["data"]["processing_status"] == "PROCESSING"

    # Evidence upload (validated + quarantined, no public copy yet)
    upload = await client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("slip.png", PNG, "image/png")},
        data={"media_type": "TRANSFER_SLIP"},
        headers=_auth(token),
    )
    assert upload.status_code == 202, upload.text

    # Pre-publish: description hidden, no evidence exposed
    pending = (await client.get(f"/api/v1/reports/{report_id}")).json()["data"]
    assert pending["processing_status"] == "PROCESSING"
    assert pending["description"] is None
    assert pending["evidence"] == []

    # Run the async worker
    async with SessionLocal() as db:
        result = await report_pipeline.process_report(db, uuid.UUID(report_id))
    assert result == "published"

    published = (await client.get(f"/api/v1/reports/{report_id}")).json()["data"]
    assert published["processing_status"] == "PUBLISHED"
    assert published["description"]
    assert published["evidence"][0]["media_url"]
    assert published["evidence"][0]["is_blurred_pii"] is True

    # Feed surfaces the published report on the entity profile
    feed = await client.get(
        "/api/v1/entities/account",
        params={"country": "ID", "bank": "014", "account": account},
    )
    data = feed.json()["data"]
    assert data["community_signals"]["total_reports"] >= 1
    assert any(r["id"] == report_id for r in data["reports"])


async def test_fail_closed_redaction_never_publishes(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = await _token(client, "failclosed@trustpay.dev")
    account = "8440002233"
    created = await client.post("/api/v1/reports", json=_payload(account), headers=_auth(token))
    report_id = created.json()["data"]["report_id"]
    await client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("slip.png", PNG, "image/png")},
        headers=_auth(token),
    )

    def _boom(_: bytes) -> bytes:
        raise report_pipeline.vision.RedactionError("simulated failure")

    monkeypatch.setattr(report_pipeline.vision, "redact_image", _boom)

    async with SessionLocal() as db:
        result = await report_pipeline.process_report(db, uuid.UUID(report_id))
    assert result == "failed"

    report = (await client.get(f"/api/v1/reports/{report_id}")).json()["data"]
    assert report["processing_status"] == "FAILED"
    assert report["evidence"] == []  # never publish unredacted evidence


async def test_evidence_upload_rejects_non_image(client: httpx.AsyncClient) -> None:
    token = await _token(client, "badupload@trustpay.dev")
    created = await client.post(
        "/api/v1/reports", json=_payload("8330001212"), headers=_auth(token)
    )
    report_id = created.json()["data"]["report_id"]
    resp = await client.post(
        f"/api/v1/reports/{report_id}/evidence",
        files={"file": ("x.png", b"not an image", "image/png")},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_duplicate_evidence_detected(client: httpx.AsyncClient) -> None:
    token = await _token(client, "dupimage@trustpay.dev")
    slip = _synthetic_png(seed=137)  # unique image so cross-test evidence can't collide
    ids = []
    for account in ("8111111111", "8222222222"):
        created = await client.post("/api/v1/reports", json=_payload(account), headers=_auth(token))
        report_id = created.json()["data"]["report_id"]
        await client.post(
            f"/api/v1/reports/{report_id}/evidence",
            files={"file": ("slip.png", slip, "image/png")},
            headers=_auth(token),
        )
        ids.append(report_id)

    async with SessionLocal() as db:
        await report_pipeline.process_report(db, uuid.UUID(ids[0]))
        await report_pipeline.process_report(db, uuid.UUID(ids[1]))

    async with SessionLocal() as db:
        row = await db.get(FraudReport, uuid.UUID(ids[1]))
    assert row.processing_status == "PUBLISHED"
    assert ids[0] in row.ai_forensic_notes["duplicate_evidence_of"]
