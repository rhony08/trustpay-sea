"""Community extras: Scam Playbook library, quiz, and Diligence Receipts (Phase 3B.7/3B.10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.enums import EntityType, RiskLevel, Scheme
from app.resolver.banks import UnsupportedBankError, get_institution
from app.resolver.normalize import NormalizationError, normalize_account
from app.services.entity_service import get_entity_by_hash
from app.services.playbook import get_playbook, list_playbooks
from app.services.receipt import ReceiptError, create_receipt, verify_receipt
from app.services.scam_quiz import public_questions

router = APIRouter(tags=["community"])


@router.get("/playbook")
async def playbooks():
    return {"status": "success", "data": {"playbooks": list_playbooks()}}


@router.get("/playbook/{category}")
async def playbook(category: str):
    entry = get_playbook(category)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown category")
    return {"status": "success", "data": entry}


@router.get("/quiz")
async def quiz():
    return {"status": "success", "data": {"questions": public_questions()}}


@router.post("/receipts/account")
async def create_account_receipt(
    country: str, bank: str, account: str, db: AsyncSession = Depends(get_db)
):
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
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "no registry entry to certify for this identifier"
        )

    subject = {
        "entity_type": entity.entity_type,
        "scheme": entity.scheme,
        "country": entity.country_code,
        "institution": entity.institution_code,
        "account_masked": entity.account_masked,
        "risk_score": entity.risk_score,
        "risk_level": RiskLevel.from_score(entity.risk_score).value,
    }
    token, payload = create_receipt(settings.receipt_signing_key, subject=subject)
    return {"status": "success", "data": {"token": token, "receipt": payload}}


@router.get("/receipts/{token}")
async def read_receipt(token: str):
    try:
        payload = verify_receipt(get_settings().receipt_signing_key, token)
    except ReceiptError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "success", "data": payload}
