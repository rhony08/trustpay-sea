"""Resolver API tests (Phase 1.5): exact-match lookup, not-found, ADR-016 labels.

Anonymous lookups must never create rows — assert DB row count is unchanged
after a not-found lookup (Doc 02 §10.3).
"""

from pathlib import Path

import httpx
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import EntityType, HolderNameSource, Scheme
from app.models import PaymentEntity
from app.resolver.banks import get_institution
from app.resolver.normalize import normalize_account, normalize_qr_identifier
from app.services.entity_service import upsert_entity

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
QRIS = (VECTORS / "qris_static.txt").read_text().strip()


async def _seed_entity(**overrides) -> PaymentEntity:
    settings = get_settings()
    inst = get_institution("ID", "014")
    account_hash, masked = normalize_account(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=inst,
        account_raw="8830192831",
        kms_key=settings.account_hmac_key,
    )
    async with SessionLocal() as db:
        return await upsert_entity(
            db,
            entity_type=EntityType.BANK_ACCOUNT,
            scheme=Scheme.BANK,
            country_code="ID",
            institution_code="014",
            account_hash=account_hash,
            account_masked=masked,
            **overrides,
        )


async def test_account_lookup_miss_never_inserts(client: httpx.AsyncClient) -> None:
    async with SessionLocal() as db:
        before = await db.scalar(select(func.count(PaymentEntity.id)))

    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "9999999999"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_found"
    assert body["data"]["in_registry"] is False
    assert body["data"]["query"]["account_masked"] == "999-****-999"

    async with SessionLocal() as db:
        after = await db.scalar(select(func.count(PaymentEntity.id)))
    assert before == after, "anonymous lookup must not create entities (§10.3)"


async def test_account_lookup_hit_masked(client: httpx.AsyncClient) -> None:
    await _seed_entity()
    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "8830192831"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["entity"]["account_masked"] == "883-****-831"
    assert data["entity"]["institution"] == "014"
    assert data["risk_assessment"]["risk_score"] == 15
    assert data["risk_assessment"]["risk_level"] == "LOW_RISK"
    # C5: brand-new entity shows Amber "Unverified", never green
    assert data["risk_assessment"]["badge"] == {"color": "AMBER", "label": "Unverified"}
    assert data["community_signals"]["total_reports"] == 0


async def test_formatting_variants_hit_same_entity(client: httpx.AsyncClient) -> None:
    await _seed_entity()
    for raw in ("883-0192-831", "883 0192 831", "8830192831"):
        resp = await client.get(
            "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": raw}
        )
        assert resp.json()["status"] == "success", f"variant {raw!r} missed"


async def test_unsupported_bank_400(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "999", "account": "8830192831"}
    )
    assert resp.status_code == 400
    assert "unsupported bank" in resp.json()["detail"]


async def test_bad_length_400(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "12"}
    )
    assert resp.status_code == 400
    assert "length" in resp.json()["detail"]


async def test_qr_screen_miss_includes_metadata(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/entities/qr", json={"qr_payload": QRIS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_found"
    meta = body["data"]["qr_metadata"]
    assert meta["merchant_name"] == "CV ELEKTRONIK JAYA MURAH"
    assert meta["national_merchant_id"] == "936009140021948201"
    assert meta["scheme"] == "QRIS"
    assert meta["homoglyph_warning"] is False


async def test_qr_screen_hit(client: httpx.AsyncClient) -> None:
    settings = get_settings()
    account_hash, masked = normalize_qr_identifier(
        country="ID",
        scheme=Scheme.QRIS,
        nmid="936009140021948201",
        kms_key=settings.account_hmac_key,
    )
    async with SessionLocal() as db:
        await upsert_entity(
            db,
            entity_type=EntityType.QR_CODE,
            scheme=Scheme.QRIS,
            country_code="ID",
            institution_code=None,
            account_hash=account_hash,
            account_masked=masked,
            merchant_name="CV ELEKTRONIK JAYA MURAH",
            merchant_city="JAKARTA",
            nmid="936009140021948201",
        )
    resp = await client.post("/api/v1/entities/qr", json={"qr_payload": QRIS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["entity"]["merchant_name"] == "CV ELEKTRONIK JAYA MURAH"
    assert body["data"]["entity"]["account_masked"] == "NMID ****8201"


async def test_bad_crc_400(client: httpx.AsyncClient) -> None:
    corrupted = QRIS[:-4] + "0000"
    resp = await client.post("/api/v1/entities/qr", json={"qr_payload": corrupted})
    assert resp.status_code == 400
    assert "CRC" in resp.json()["detail"]


async def test_adr016_holder_label_verified_vs_reported(client: httpx.AsyncClient) -> None:
    """Verified owner → 'Verified owner name'; otherwise → reported-name label."""
    entity = await _seed_entity()
    async with SessionLocal() as db:
        from app.models import PaymentEntity as PE

        row = await db.get(PE, entity.id)
        row.holder_name = "Budi Santoso"
        row.holder_name_source = HolderNameSource.COMMUNITY_REPORTED
        row.is_owner_verified = False
        await db.commit()

    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "8830192831"}
    )
    holder = resp.json()["data"]["entity"]["holder"]
    assert holder["label"].startswith("Reported recipient name")
    assert holder["confidence"] == "UNVERIFIED"
    assert "verify independently" in holder["label"]

    async with SessionLocal() as db:
        row = await db.get(PaymentEntity, entity.id)
        row.holder_name_source = HolderNameSource.OWNER_KYC_PROOF
        row.is_owner_verified = True
        await db.commit()

    resp = await client.get(
        "/api/v1/entities/account", params={"country": "ID", "bank": "014", "account": "8830192831"}
    )
    holder = resp.json()["data"]["entity"]["holder"]
    assert holder == {
        "name": "Budi Santoso",
        "label": "Verified owner name",
        "confidence": "VERIFIED",
    }
