"""Controlled bank/institution reference API (Phase 1.1).

The reporting UI must populate its institution picker from here — a report may
only reference an institution that exists in the seeded ``banks`` table, never
free text. Public (no auth): the directory is non-sensitive reference data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Bank
from app.resolver.banks import SUPPORTED_COUNTRIES

router = APIRouter(tags=["reference"])


@router.get("/banks")
async def list_banks(
    country: str | None = Query(default=None, description="ISO-3166 alpha-2, e.g. ID"),
    bank_type: str | None = Query(default=None, description="COMMERCIAL | E_WALLET | ..."),
    q: str | None = Query(default=None, max_length=100, description="name/alias substring"),
    db: AsyncSession = Depends(get_db),
):
    if country and country.upper() not in SUPPORTED_COUNTRIES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unsupported country: {country} (supported: {', '.join(SUPPORTED_COUNTRIES)})",
        )

    stmt = select(Bank).where(Bank.is_active.is_(True))
    if country:
        stmt = stmt.where(Bank.country_code == country.upper())
    if bank_type:
        stmt = stmt.where(Bank.bank_type == bank_type.upper())
    if q:
        stmt = stmt.where(Bank.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Bank.country_code, Bank.sort_order)

    rows = (await db.scalars(stmt)).all()
    banks = [
        {
            "country": row.country_code,
            "code": row.code,
            "name": row.name,
            "short_name": row.short_name,
            "bank_type": row.bank_type,
            "bic": row.bic,
            "national_id": row.national_id,
            "min_length": row.min_length,
            "max_length": row.max_length,
        }
        for row in rows
    ]
    return {"status": "success", "data": {"count": len(banks), "banks": banks}}
