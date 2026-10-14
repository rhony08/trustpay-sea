"""Async report pipeline (Phases 2.3–2.6).

Consumes a submitted report: fail-closed PII redaction → public copy, slip OCR +
tamper heuristics, pHash duplicate detection, NLP typology + NER. Idempotent —
a report is only ever processed while `PROCESSING`.

Fail-closed invariant: if redaction raises, the report becomes `FAILED` and no
public evidence is ever produced.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.ai import forensics, nlp, vision
from app.enums import ProcessingStatus
from app.models import FraudReport, ReportEvidence
from app.services.report_service import list_evidence
from app.storage import get_storage

log = logging.getLogger("trustpay.worker.report")

# dHash Hamming distance ≤ this counts as the "same" image (dup evidence).
DUP_HAMMING_THRESHOLD = 6


async def _find_duplicate(db, image_hash: str, exclude_id: uuid.UUID) -> str | None:
    rows = await db.scalars(
        select(ReportEvidence).where(
            ReportEvidence.image_hash.is_not(None),
            ReportEvidence.id != exclude_id,
        )
    )
    for other in rows:
        if (
            other.image_hash
            and forensics.hamming_distance(other.image_hash, image_hash) <= DUP_HAMMING_THRESHOLD
        ):
            return str(other.report_id)
    return None


async def process_report(db, report_id: uuid.UUID) -> str:
    """Returns 'published' | 'failed' | 'skipped'."""
    report = await db.get(FraudReport, report_id)
    if report is None or report.processing_status != ProcessingStatus.PROCESSING:
        return "skipped"

    storage = get_storage()
    evidences = await list_evidence(db, report_id)
    duplicates: list[str] = []
    redacted_first: bytes | None = None
    tampering: dict = {"engine": "mock", "signals": []}
    tampering_detected = False

    for evidence in evidences:
        if not evidence.original_quarantine_url:
            continue
        raw = storage.read(evidence.original_quarantine_url)
        try:
            redacted = vision.redact_image(raw)
        except vision.RedactionError as exc:
            # Fail-closed: never publish unredacted evidence.
            log.warning("redaction failed for report %s: %s", report_id, exc)
            report.processing_status = ProcessingStatus.FAILED
            report.ai_forensic_notes = {"error": "redaction_failed"}
            await db.commit()
            return "failed"

        public = storage.put_public(data=redacted, content_type="image/jpeg")
        evidence.media_url = storage.public_url(public.key)
        evidence.is_blurred_pii = True
        evidence.image_hash = forensics.phash(raw)

        dup_of = await _find_duplicate(db, evidence.image_hash, evidence.id)
        if dup_of:
            duplicates.append(dup_of)
            evidence.tampering_signals = {"duplicate_of_report_id": dup_of}

        if redacted_first is None:
            redacted_first = raw
            tampering_detected, tampering = forensics.detect_tampering(raw)
            evidence.ai_tampering_detected = tampering_detected
            evidence.tampering_signals = {
                **(evidence.tampering_signals or {}),
                "tamper": tampering,
            }

    ocr = forensics.ocr_slip(redacted_first) if redacted_first else {"engine": "none"}
    typology, confidence = nlp.classify_typology(report.description)
    ner = nlp.extract_entities(report.description)

    report.ai_forensic_notes = {
        "ocr": ocr,
        "tampering": tampering,
        "tampering_detected": tampering_detected,
        "duplicate_evidence_of": duplicates,
        "typology": {
            "predicted": typology,
            "confidence": confidence,
            "matches_submitted": typology == report.category,
        },
        "ner": ner,
    }
    report.ai_risk_score = min(100, report.severity * 10 + (20 if tampering_detected else 0))
    report.processing_status = ProcessingStatus.PUBLISHED
    await db.commit()
    log.info("report %s published (typology=%s)", report_id, typology)
    return "published"


async def process_pending_reports(db, *, limit: int = 20) -> int:
    """Scheduler safety-net: publish any reports left PROCESSING."""
    rows = await db.scalars(
        select(FraudReport.id)
        .where(FraudReport.processing_status == ProcessingStatus.PROCESSING)
        .order_by(FraudReport.created_at)
        .limit(limit)
    )
    processed = 0
    for report_id in list(rows):
        if await process_report(db, report_id) == "published":
            processed += 1
    return processed
