"""Public Screen API (Phase 9 / docs/09).

Keyless **visitor** tier and keyed **demo/partner/enterprise** tiers. Responses
are privacy-safe: masked profile + risk band only — **never** holder names or PII
(ADR-016 holder reveal is a first-party UI privilege, not an API feature).
Visitor counts are bucketed; keyed calls get exact counts + search intelligence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.entities import _government_check
from app.config import get_settings
from app.core.api_keys import (
    VISITOR_TIER,
    ScreenCaller,
    consume_quota,
    daily_limit,
    distinct_entities_this_hour,
    lookup_api_key,
    now_utc,
)
from app.db import get_db
from app.enums import EntityType, RiskLevel, Scheme
from app.resolver.banks import UnsupportedBankError, get_institution
from app.resolver.emvco import EMVCoParseError, parse_emvco
from app.resolver.normalize import NormalizationError, normalize_account, normalize_qr_identifier
from app.services.entity_service import _report_stats, get_entity_by_hash
from app.services.phone_search import search_phone
from app.services.search_intel import get_search_intel

router = APIRouter(prefix="/screen", tags=["screen"])


class QRScreenRequest(BaseModel):
    qr_payload: str = Field(min_length=1, max_length=512)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_headers(response: Response, caller: ScreenCaller) -> None:
    if caller.limit is not None:
        response.headers["X-RateLimit-Limit"] = str(caller.limit)
        response.headers["X-RateLimit-Remaining"] = str(caller.remaining or 0)
    response.headers["X-TrustPay-Tier"] = caller.tier


async def _caller(request: Request, db: AsyncSession) -> ScreenCaller:
    redis = request.app.state.redis
    raw = request.headers.get("X-API-Key")
    api_key = None
    if raw:
        api_key = await lookup_api_key(db, raw)
        if api_key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or revoked API key")
        if "screen:read" not in (api_key.scopes or []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "key lacks screen:read scope")
        api_key.last_used_at = now_utc()
        await db.commit()
        tier = api_key.tier
        identity = f"key:{api_key.key_hash}"
    else:
        tier = VISITOR_TIER
        identity = f"visitor:{_client_ip(request)}"

    allowed, remaining, limit = await consume_quota(
        redis, identity=identity, limit=daily_limit(tier)
    )
    if not allowed:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "daily screen quota exceeded")
    return ScreenCaller(
        tier=tier, identity=identity, limit=limit, remaining=remaining, api_key=api_key
    )


async def _probe(request: Request, caller: ScreenCaller, entity_ref: str) -> None:
    settings = get_settings()
    redis = request.app.state.redis
    count = await distinct_entities_this_hour(
        redis, identity=caller.identity, entity_ref=entity_ref
    )
    threshold = (
        settings.screen_probe_visitor_distinct_per_hour
        if caller.tier == VISITOR_TIER
        else settings.screen_probe_key_distinct_per_hour
    )
    if count > threshold:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "unusual screening pattern detected — challenge required",
            headers={"X-Challenge-Required": "true"},
        )


def _bucket(count: int) -> str:
    if count < 10:
        return "<10"
    if count < 100:
        return "10+"
    return "100+"


def _entity_block(entity) -> dict:
    return {
        "entity_type": entity.entity_type,
        "scheme": entity.scheme,
        "country": entity.country_code,
        "institution": entity.institution_code,
        "account_masked": entity.account_masked,
        "merchant_name": entity.merchant_name,
        "merchant_city": entity.merchant_city,
        "nmid": entity.nmid,
    }


async def _screen_response(
    db: AsyncSession,
    caller: ScreenCaller,
    entity,
    *,
    query: dict,
    gov_check: dict | None,
) -> dict:
    visitor = caller.tier == VISITOR_TIER
    total, verified, _velocity = await _report_stats(db, entity.id)
    data = {
        "entity": _entity_block(entity),
        "risk": {
            "score": entity.risk_score,
            "level": RiskLevel.from_score(entity.risk_score).value,
            "is_gov_blacklisted": entity.is_gov_blacklisted,
            "is_under_dispute": entity.is_under_dispute,
            "anomaly_spike_detected": entity.anomaly_spike_detected,
        },
        "signals": {
            "total_reports": _bucket(total) if visitor else total,
            "admin_verified_reports": _bucket(verified) if visitor else verified,
        },
        "tier": caller.tier,
        "query": query,
        "note": "Risk score is 0-100; higher = riskier.",
    }
    if not visitor:
        data["search_intelligence"] = await get_search_intel(db, entity.id)
    if gov_check is not None:
        data["gov_check"] = gov_check
    return data


@router.get("/account")
async def screen_account(
    request: Request,
    response: Response,
    country: str,
    bank: str,
    account: str,
    db: AsyncSession = Depends(get_db),
):
    caller = await _caller(request, db)
    _set_headers(response, caller)

    settings = get_settings()
    try:
        institution = get_institution(country, bank)
    except UnsupportedBankError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"unsupported bank: {country}:{bank}"
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

    await _probe(request, caller, account_hash)
    gov_check = await _government_check(country, institution, account)
    query = {
        "country": country.upper(),
        "institution": institution.name,
        "account_masked": masked,
    }
    entity = await get_entity_by_hash(db, account_hash)
    if entity is None:
        return {
            "status": "not_found",
            "data": {
                "in_registry": False,
                "query": query,
                "gov_check": gov_check,
                "tier": caller.tier,
            },
        }
    return {
        "status": "success",
        "data": await _screen_response(db, caller, entity, query=query, gov_check=gov_check),
    }


@router.get("/phone")
async def screen_phone(
    request: Request,
    response: Response,
    country: str,
    phone: str,
    db: AsyncSession = Depends(get_db),
):
    """Aggregated e-wallet screen by phone number (all wallets for that number)."""
    caller = await _caller(request, db)
    _set_headers(response, caller)
    data = await search_phone(db, country=country, phone=phone)
    if caller.tier == VISITOR_TIER:
        for wallet in data["wallets"]:
            wallet["total_reports"] = _bucket(wallet["total_reports"])
        data["totals"]["total_reports"] = _bucket(data["totals"]["total_reports"])
    data["tier"] = caller.tier
    data["note"] = "Risk score is 0-100; higher = riskier."
    return {"status": "success" if data["wallet_count"] else "not_found", "data": data}


@router.post("/qr")
async def screen_qr(
    body: QRScreenRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    caller = await _caller(request, db)
    _set_headers(response, caller)

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
    await _probe(request, caller, account_hash)
    query = {
        "country": country,
        "scheme": parsed.scheme.value,
        "merchant_name": parsed.merchant_name,
        "account_masked": masked,
    }
    entity = await get_entity_by_hash(db, account_hash)
    if entity is None:
        return {
            "status": "not_found",
            "data": {"in_registry": False, "query": query, "tier": caller.tier},
        }
    return {
        "status": "success",
        "data": await _screen_response(db, caller, entity, query=query, gov_check=None),
    }
