"""Data retention & legal-hold job (Phase 10 / docs/10).

Per-table fate matrix, defaults N = 90 days:
- original (quarantine) evidence objects are purged and their reference nulled;
  redacted public copies are kept.
- report bodies are tombstoned (description/amount nulled, `deleted_at` set) but
  stay countable for scoring integrity (category/severity/timestamps kept).
- precedence: **legal hold > dispute freeze > retention** — held reports and
  entities under dispute are exempt.
- dry-run by default (`RETENTION_DRY_RUN=true`) — logs candidates without deleting.
- every run is written to the hash-chained audit log.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import append_audit
from app.enums import ProcessingStatus
from app.models import FraudReport, PaymentEntity, ReportEvidence
from app.storage import StorageError, get_storage


async def _candidate_reports(db: AsyncSession, cutoff: datetime) -> list[FraudReport]:
    rows = await db.scalars(
        select(FraudReport)
        .join(PaymentEntity, PaymentEntity.id == FraudReport.payment_entity_id)
        .where(
            FraudReport.created_at < cutoff,
            FraudReport.processing_status == ProcessingStatus.PUBLISHED,
            FraudReport.is_legal_hold.is_(False),
            PaymentEntity.is_under_dispute.is_(False),
        )
    )
    return list(rows)


async def run_retention(db: AsyncSession, *, dry_run: bool | None = None) -> dict:
    settings = get_settings()
    dry = settings.retention_dry_run if dry_run is None else dry_run
    cutoff = datetime.now(UTC) - timedelta(days=settings.retention_evidence_days)

    reports = await _candidate_reports(db, cutoff)
    report_ids = [r.id for r in reports]
    evidence: list[ReportEvidence] = []
    if report_ids:
        evidence = list(
            await db.scalars(select(ReportEvidence).where(ReportEvidence.report_id.in_(report_ids)))
        )

    evidence_eligible = [e for e in evidence if e.original_quarantine_url]
    tomb_eligible = [
        r
        for r in reports
        if r.deleted_at is None and (r.description is not None or r.loss_amount is not None)
    ]

    result = {
        "dry_run": dry,
        "cutoff": cutoff.isoformat(),
        "evidence_eligible": len(evidence_eligible),
        "reports_eligible": len(tomb_eligible),
        "evidence_purged": 0,
        "reports_tombstoned": 0,
    }

    if dry:
        await append_audit(
            db,
            action="retention.dry_run",
            note=f"evidence={len(evidence_eligible)} reports={len(tomb_eligible)}",
        )
        return result

    storage = get_storage()
    now = datetime.now(UTC)
    for item in evidence_eligible:
        with contextlib.suppress(StorageError):
            storage.delete(item.original_quarantine_url)
        item.original_quarantine_url = None
        result["evidence_purged"] += 1
    for report in tomb_eligible:
        report.description = None
        report.loss_amount = None
        report.deleted_at = now
        result["reports_tombstoned"] += 1
    await db.commit()

    note = (
        f"evidence={result['evidence_purged']} reports={result['reports_tombstoned']} "
        f"days={settings.retention_evidence_days}"
    )
    await append_audit(db, action="retention.purged", note=note)
    return result
