"""Payment identity resolver API (Phase 1).

- GET  /api/v1/entities/account  — exact-match bank/e-wallet lookup
- POST /api/v1/entities/qr       — EMVCo payload screen (parsed server-side)
- POST /api/v1/qr/decode         — QR image → EMVCo payload + metadata

All lookups are exact-match on the KMS-keyed hash. Anonymous lookups never
create rows (Doc 02 §10.3). Holder-name reveal = ADR-016 (exact-match only).
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.enums import EntityType, Scheme
from app.resolver.banks import UnsupportedBankError, get_institution
from app.resolver.emvco import (
    EMVCoParseError,
    ParsedQR,
    has_homoglyph_risk,
    normalize_merchant_name,
    parse_emvco,
)
from app.resolver.normalize import NormalizationError, normalize_account, normalize_qr_identifier
from app.resolver.qr_image import QRDecodeError, decode_qr_payload
from app.services.entity_service import (
    _report_stats,
    build_profile,
    get_entity_by_hash,
    not_found_profile,
)
from app.services.intel_service import get_entity_intel
from app.services.report_service import (
    evidence_for_reports,
    list_published_reports,
    serialize_report,
)
from app.services.search_intel import record_search

router = APIRouter(tags=["resolver"])


async def _published_reports(db, entity_id) -> list[dict]:
    reports = await list_published_reports(db, entity_id)
    evidence = await evidence_for_reports(db, [r.id for r in reports])
    feed = []
    for report in reports:
        items = evidence.get(report.id, [])
        feed.append(serialize_report(report, items, public_urls={e.id: e.media_url for e in items}))
    return feed


class AccountLookupResponse(BaseModel):
    status: str = "success"
    data: dict


class QRScreenRequest(BaseModel):
    qr_payload: str | None = Field(default=None, min_length=1, max_length=512)
    qr_image_base64: str | None = None


def _qr_metadata(parsed: ParsedQR, *, payload: str | None = None, entity=None) -> dict:
    changed = bool(
        entity is not None
        and entity.emvco_payload
        and payload is not None
        and entity.emvco_payload != payload
    )
    return {
        "scheme": parsed.scheme.value,
        "point_of_initiation": parsed.point_of_initiation,
        "merchant_name": parsed.merchant_name,
        "merchant_city": parsed.merchant_city,
        "national_merchant_id": parsed.nmid,
        "mcc": parsed.mcc,
        "currency": parsed.currency,
        "amount": parsed.amount,
        "country": parsed.country,
        "homoglyph_warning": has_homoglyph_risk(parsed.merchant_name),
        "normalized_merchant_name": normalize_merchant_name(parsed.merchant_name),
        "qr_changed_since_last_seen": changed,
    }


@router.get("/entities/account", response_model=AccountLookupResponse)
async def lookup_account(
    request: Request,
    country: str,
    bank: str,
    account: str,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    try:
        institution = get_institution(country, bank)
    except UnsupportedBankError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unsupported bank: {country}:{bank}",
        ) from exc

    try:
        account_hash, masked = normalize_account(
            country=country,
            scheme=Scheme.BANK,
            entity_type=EntityType.BANK_ACCOUNT,
            institution=institution,
            account_raw=account,
            kms_key=settings.account_hmac_key,
        )
    except NormalizationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    entity = await get_entity_by_hash(db, account_hash)
    query = {
        "country": country.upper(),
        "institution": institution.name,
        "account_masked": masked,
    }
    if entity is None:
        return {"status": "not_found", "data": not_found_profile(query)}

    await record_search(db, entity.id)
    total, verified, velocity = await _report_stats(db, entity.id)
    intel = await get_entity_intel(
        db,
        request.app.state.redis,
        entity,
        total_reports=total,
        admin_verified_reports=verified,
        report_velocity_7d=velocity,
    )
    return {
        "status": "success",
        "data": {
            **build_profile(
                entity,
                total_reports=total,
                admin_verified_reports=verified,
                report_velocity_7d=velocity,
                reports=await _published_reports(db, entity.id),
            ),
            **intel,
            "query": query,
        },
    }


@router.post("/entities/qr", response_model=AccountLookupResponse)
async def screen_qr(body: QRScreenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if not body.qr_payload:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "qr_payload required (image decode lands via /qr/decode)",
        )
    try:
        parsed = parse_emvco(body.qr_payload)
    except EMVCoParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid EMVCo payload: {exc}") from exc

    settings = get_settings()
    country = parsed.country or "ID"
    account_hash, masked = normalize_qr_identifier(
        country=country,
        scheme=parsed.scheme,
        nmid=parsed.nmid or "",
        kms_key=settings.account_hmac_key,
    )
    entity = await get_entity_by_hash(db, account_hash)
    metadata = _qr_metadata(parsed, payload=body.qr_payload, entity=entity)
    query = {"masked_method": f"{parsed.scheme.value} code {parsed.merchant_name or ''}".strip()}
    if entity is None:
        return {
            "status": "not_found",
            "data": {**not_found_profile(query), "qr_metadata": metadata},
        }

    await record_search(db, entity.id)
    total, verified, velocity = await _report_stats(db, entity.id)
    intel = await get_entity_intel(
        db,
        request.app.state.redis,
        entity,
        total_reports=total,
        admin_verified_reports=verified,
        report_velocity_7d=velocity,
    )
    return {
        "status": "success",
        "data": {
            **build_profile(
                entity,
                total_reports=total,
                admin_verified_reports=verified,
                report_velocity_7d=velocity,
                reports=await _published_reports(db, entity.id),
            ),
            **intel,
            "qr_metadata": metadata,
            "query": query,
        },
    }


@router.post("/qr/decode")
async def decode_qr(file: UploadFile = File(...)):
    """Server-authoritative QR decode (ADR-001): client previews, server decides."""
    image_bytes = await file.read()
    try:
        payload = decode_qr_payload(image_bytes)
    except QRDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    try:
        parsed = parse_emvco(payload)
        return {
            "status": "success",
            "data": {"qr_payload": payload, "qr_metadata": _qr_metadata(parsed)},
        }
    except EMVCoParseError as exc:
        # decoded but not EMVCo — still return the raw string so the UI can explain
        return {
            "status": "decoded_not_emvco",
            "data": {"qr_payload": payload, "detail": str(exc)},
        }
