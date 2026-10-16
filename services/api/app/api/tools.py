"""Security-awareness tools API (Phase 4B): deal checker, hotlines, recovery, warning card."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_ai_provider
from app.ai.providers.mock import MockProvider
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


class MessageAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/tools/too-good-to-be-true")
async def too_good_to_be_true(body: DealCheckRequest):
    """Explainable scam-tactics check. Uses the configured AI provider when set;
    falls back to the local heuristic so the tool never fails closed on the user."""
    provider = get_ai_provider()
    try:
        data = await provider.judge_deal(body.text)
    except Exception:  # noqa: BLE001 — degrade to heuristic, never 500
        data = check_too_good_to_be_true(body.text)
    return {"status": "success", "data": data}


@router.post("/tools/analyze-message")
async def analyze_message(body: MessageAnalyzeRequest):
    """Analyze a suspicious message/chat log for social-engineering signals and
    extract payment coordinates (the artifact-first replacement for generic
    fact-check lookup). Falls back to the local heuristic on provider error."""
    provider = get_ai_provider()
    try:
        data = await provider.analyze_message(body.text)
    except Exception:  # noqa: BLE001 — degrade to heuristic, never 500
        data = await MockProvider().analyze_message(body.text)
    return {"status": "success", "data": data}


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
