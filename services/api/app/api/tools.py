"""Security-awareness tools API (Phase 4B): deal checker, hotlines, recovery, warning card."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.enums import EntityType, RiskLevel, Scheme
from app.resolver.banks import UnsupportedBankError, get_institution
from app.resolver.normalize import NormalizationError, normalize_account
from app.services.entity_service import get_entity_by_hash
from app.services.receipt import create_receipt
from app.services.safety_tools import check_too_good_to_be_true, hotlines_for, recovery_plan

router = APIRouter(tags=["tools"])


class DealCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/tools/too-good-to-be-true")
async def too_good_to_be_true(body: DealCheckRequest):
    return {"status": "success", "data": check_too_good_to_be_true(body.text)}


@router.get("/hotlines")
async def hotlines(country: str):
    return {
        "status": "success",
        "data": {"country": country.upper(), "hotlines": hotlines_for(country)},
    }


@router.get("/recovery")
async def recovery(country: str, bank: str | None = None):
    return {"status": "success", "data": recovery_plan(country, bank)}


@router.get("/tools/warning-card")
async def warning_card(country: str, bank: str, account: str, db: AsyncSession = Depends(get_db)):
    """Signed share link + risk for an entity (QR/card rendered client-side)."""
    settings = get_settings()
    try:
        institution = get_institution(country, bank)
        account_hash, _masked = normalize_account(
            country=country,
            scheme=Scheme.BANK,
            entity_type=EntityType.BANK_ACCOUNT,
            institution=institution,
            account_raw=account,
            kms_key=settings.account_hmac_key,
        )
    except (UnsupportedBankError, NormalizationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    entity = await get_entity_by_hash(db, account_hash)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no registry entry for this identifier")

    subject = {
        "entity_type": entity.entity_type,
        "scheme": entity.scheme,
        "country": entity.country_code,
        "institution": entity.institution_code,
        "account_masked": entity.account_masked,
        "risk_score": entity.risk_score,
        "risk_level": RiskLevel.from_score(entity.risk_score).value,
    }
    token, receipt = create_receipt(settings.receipt_signing_key, subject=subject)
    return {
        "status": "success",
        "data": {
            "token": token,
            "receipt": receipt,
            "share_path": f"/warning?token={token}",
        },
    }
