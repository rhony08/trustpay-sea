"""Demo seed script tests (Phase 7.3)."""

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import FraudReport, PaymentEntity
from app.seeds.seed_demo import seed_demo


async def test_seed_demo_is_idempotent() -> None:
    async with SessionLocal() as db:
        first = await seed_demo(db)
    if first.get("skipped"):
        # A previous test/run already seeded; assert the data is present.
        async with SessionLocal() as db:
            assert await db.scalar(select(func.count(PaymentEntity.id))) >= 10
        return

    assert first["entities"] == 10
    assert first["admin_email"] == "analyst@trustpay.dev"

    async with SessionLocal() as db:
        second = await seed_demo(db)
        entities = await db.scalar(select(func.count(PaymentEntity.id)))
        reports = await db.scalar(select(func.count(FraudReport.id)))
    assert second["skipped"] is True
    assert entities >= 10
    assert reports >= 10
