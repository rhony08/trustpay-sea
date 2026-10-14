"""Seed the ``banks`` reference table from ``app/data/banks/*.json``.

Idempotent: safe to run repeatedly (upsert on ``(country_code, code)``). This is
the mechanism that keeps the reporting UI's institution list a controlled
vocabulary — a report can only reference a bank present here.

Usage:
    python -m app.seeds.seed_banks
"""

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bank
from app.resolver.banks import load_bank_records

log = logging.getLogger("trustpay.seed.banks")


async def seed_banks(db: AsyncSession) -> int:
    """Upsert every reference record; returns the number processed."""
    order_by_country: dict[str, int] = {}
    records = load_bank_records()
    for record in records:
        country = record["country_code"].upper()
        sort_order = order_by_country.get(country, 0)
        order_by_country[country] = sort_order + 1

        values = {
            "country_code": country,
            "code": record["code"],
            "name": record["name"],
            "short_name": record.get("short_name"),
            "bic": record.get("bic"),
            "national_id": record.get("national_id"),
            "bank_type": record["bank_type"],
            "min_length": record.get("min_length"),
            "max_length": record.get("max_length"),
            "aliases": record.get("aliases") or [],
            "is_active": True,
            "sort_order": sort_order,
        }
        stmt = pg_insert(Bank).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_banks_country_code",
            set_={k: stmt.excluded[k] for k in values if k not in ("country_code", "code")},
        )
        await db.execute(stmt)

    await db.commit()
    log.info("seeded %d bank reference records", len(records))
    return len(records)


async def _main() -> None:
    from app.db import SessionLocal, engine

    async with SessionLocal() as db:
        count = await seed_banks(db)
    await engine.dispose()
    print(f"seeded {count} bank reference records")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
