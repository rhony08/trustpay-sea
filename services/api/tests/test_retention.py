"""Data retention / legal-hold tests (Phase 10 / docs/10)."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.core import audit
from app.db import SessionLocal
from app.enums import EntityType, ProcessingStatus, ReportStatus, Scheme
from app.models import FraudReport, PaymentEntity, ReportEvidence
from app.services.retention import run_retention


async def _seed_report(
    *,
    days_old: int = 91,
    legal_hold: bool = False,
    disputed: bool = False,
    with_evidence: bool = True,
) -> tuple[uuid.UUID, uuid.UUID, Path | None]:
    settings = get_settings()
    quarantine_key = f"quarantine/{uuid.uuid4().hex}.jpg"
    quarantine_path = None
    if with_evidence:
        quarantine_path = Path(settings.evidence_local_dir) / quarantine_key
        quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        quarantine_path.write_bytes(b"original-evidence")

    async with SessionLocal() as db:
        entity = PaymentEntity(
            entity_type=EntityType.BANK_ACCOUNT.value,
            scheme=Scheme.BANK.value,
            country_code="ID",
            institution_code="014",
            account_hash=uuid.uuid4().hex,
            account_masked="100-****-999",
            is_under_dispute=disputed,
        )
        db.add(entity)
        await db.flush()
        report = FraudReport(
            payment_entity_id=entity.id,
            category="ONLINE_SHOP_GHOSTING",
            severity=3,
            description="senior retention-test narrative",
            processing_status=ProcessingStatus.PUBLISHED,
            admin_verification_status="PENDING",
            status=ReportStatus.ACTIVE,
            is_legal_hold=legal_hold,
            created_at=datetime.now(UTC) - timedelta(days=days_old),
        )
        db.add(report)
        await db.flush()
        if with_evidence:
            db.add(
                ReportEvidence(
                    report_id=report.id,
                    media_url="http://pub/redacted.jpg",
                    original_quarantine_url=quarantine_key,
                    media_type="TRANSFER_SLIP",
                    is_blurred_pii=True,
                )
            )
        await db.commit()
        return entity.id, report.id, quarantine_path


async def test_retention_dry_run_then_purge() -> None:
    _entity_id, report_id, quarantine_path = await _seed_report()

    async with SessionLocal() as db:
        dry = await run_retention(db, dry_run=True)
    assert dry["dry_run"] is True
    assert dry["evidence_eligible"] >= 1
    assert dry["reports_eligible"] >= 1
    # untouched
    assert quarantine_path is not None and quarantine_path.exists()
    async with SessionLocal() as db:
        report = await db.get(FraudReport, report_id)
        assert report.description == "senior retention-test narrative"

    async with SessionLocal() as db:
        result = await run_retention(db, dry_run=False)
        evidence = await db.scalar(
            select(ReportEvidence).where(ReportEvidence.report_id == report_id)
        )
        report = await db.get(FraudReport, report_id)
        chain_ok = await audit.verify_chain(db)
    assert result["evidence_purged"] >= 1
    assert result["reports_tombstoned"] >= 1
    assert quarantine_path is not None and not quarantine_path.exists()  # object purged
    assert evidence.original_quarantine_url is None  # reference nulled
    assert evidence.media_url == "http://pub/redacted.jpg"  # redacted copy kept
    assert report.description is None and report.deleted_at is not None  # tombstoned
    assert report.category == "ONLINE_SHOP_GHOSTING"  # still countable
    assert chain_ok is True


async def test_retention_respects_legal_hold() -> None:
    _entity_id, report_id, _ = await _seed_report(legal_hold=True)
    async with SessionLocal() as db:
        result = await run_retention(db, dry_run=False)
        report = await db.get(FraudReport, report_id)
    assert result["reports_tombstoned"] == 0
    assert report.description is not None


async def test_retention_respects_dispute_freeze() -> None:
    _entity_id, report_id, _ = await _seed_report(disputed=True)
    async with SessionLocal() as db:
        result = await run_retention(db, dry_run=False)
        report = await db.get(FraudReport, report_id)
    assert result["reports_tombstoned"] == 0
    assert report.description is not None


async def test_retention_ignores_recent_reports() -> None:
    _entity_id, report_id, _ = await _seed_report(days_old=1)
    async with SessionLocal() as db:
        result = await run_retention(db, dry_run=False)
    assert result["evidence_eligible"] == 0
    assert result["reports_eligible"] == 0
