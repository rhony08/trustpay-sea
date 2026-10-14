"""Bank reference directory tests (Phase 1.1).

Covers the canonical data loader (resolver) and the seeded ``banks`` table +
public listing endpoint that keeps reporting institutions a controlled vocab.
"""

import httpx
import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.enums import BankType
from app.models import Bank
from app.resolver.banks import (
    BANK_DIRECTORY,
    SUPPORTED_COUNTRIES,
    UnsupportedBankError,
    get_institution,
    load_bank_records,
)
from app.seeds.seed_banks import seed_banks


def test_directory_covers_all_target_markets() -> None:
    for country in SUPPORTED_COUNTRIES:
        assert any(c == country for c, _ in BANK_DIRECTORY), f"no banks for {country}"


def test_directory_has_no_duplicate_codes() -> None:
    keys = list(BANK_DIRECTORY)
    assert len(keys) == len(set(keys)), "duplicate (country, code) in bank directory"


def test_all_records_use_known_bank_type() -> None:
    known = {t.value for t in BankType}
    for record in load_bank_records():
        assert record["bank_type"] in known, record


def test_directory_is_sea_wide_not_demo_sized() -> None:
    # Regression guard: the directory must be the full SEA reference, not the
    # original 40-institution demo stub.
    assert len(BANK_DIRECTORY) >= 300


def test_preserved_codes_still_resolve() -> None:
    assert get_institution("ID", "014").name.startswith("Bank Central Asia")
    assert get_institution("ID", "009").bic == "BNINIDJA"
    assert get_institution("ID", "GOPAY").code == "GOPAY"
    assert get_institution("VN", "VCB").bic == "BFTVVNVX"
    assert get_institution("PH", "BDO").bic == "BNORPHMM"
    assert get_institution("MY", "MBB").bic == "MBBEMYKL"


def test_indonesian_code_collision_reconciled() -> None:
    # 213 is Bank SMBC Indonesia (ex-BTPN); BCA Syariah is 536 (BI sandi bank).
    assert get_institution("ID", "213").name.startswith("Bank SMBC Indonesia")
    assert get_institution("ID", "536").name == "Bank BCA Syariah"


def test_unsupported_bank_is_explicit() -> None:
    with pytest.raises(UnsupportedBankError):
        get_institution("ID", "999")


async def test_seed_banks_is_idempotent() -> None:
    async with SessionLocal() as db:
        first = await seed_banks(db)
    async with SessionLocal() as db:
        second = await seed_banks(db)
        count = await db.scalar(select(func.count(Bank.id)))
    assert first == second == count
    assert first >= 300


async def test_banks_endpoint_lists_controlled_directory(client: httpx.AsyncClient) -> None:
    async with SessionLocal() as db:
        await seed_banks(db)

    resp = await client.get("/api/v1/banks", params={"country": "ID", "bank_type": "E_WALLET"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["count"] >= 5
    assert all(b["country"] == "ID" for b in body["data"]["banks"])
    assert {"GOPAY", "OVO", "DANA"} <= {b["code"] for b in body["data"]["banks"]}


async def test_banks_endpoint_rejects_unsupported_country(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/banks", params={"country": "US"})
    assert resp.status_code == 400
    assert "unsupported country" in resp.json()["detail"]
