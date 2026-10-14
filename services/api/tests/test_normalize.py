"""Normalizer invariants (Phase 1.2, Doc 02 §2.1 + H11 collision guards)."""

import pytest

from app.enums import EntityType, Scheme
from app.resolver.banks import UnsupportedBankError, get_institution
from app.resolver.normalize import (
    NormalizationError,
    canonical_key,
    mask_account,
    normalize_account,
    normalize_qr_identifier,
    sanitize_account,
)

KEY = "test-key"


def test_formatting_variants_same_hash() -> None:
    inst = get_institution("ID", "014")
    hashes = {
        normalize_account(
            country="ID",
            scheme=Scheme.BANK,
            entity_type=EntityType.BANK_ACCOUNT,
            institution=inst,
            account_raw=raw,
            kms_key=KEY,
        )[0]
        for raw in ("014-123456-7", "014 1234567", "0141234567", "014-1234-567")
    }
    assert len(hashes) == 1, "formatting variants must hash identically"


def test_different_banks_different_hash() -> None:
    bca = get_institution("ID", "014")
    bni = get_institution("ID", "009")
    h1, _ = normalize_account(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=bca,
        account_raw="8830192831",
        kms_key=KEY,
    )
    h2, _ = normalize_account(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=bni,
        account_raw="8830192831",
        kms_key=KEY,
    )
    assert h1 != h2, "H11: institution must be part of the key"


def test_entity_type_collision_guard() -> None:
    """A bank account and a phone alias of the same digits must not collide."""
    inst = get_institution("ID", "GOPAY")
    h_account = canonical_key(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution_code="014",
        account="081234567890",
    )
    h_wallet = canonical_key(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.E_WALLET,
        institution_code="GOPAY",
        account="081234567890",
    )
    assert h_account != h_wallet
    assert inst is not None


def test_qr_nmid_never_collides_with_raw_account() -> None:
    qr_key = canonical_key(
        country="ID",
        scheme=Scheme.QRIS,
        entity_type=EntityType.QR_CODE,
        institution_code=None,
        account="936009140021948201",
    )
    acct_key = canonical_key(
        country="ID",
        scheme=Scheme.QRIS,
        entity_type=EntityType.BANK_ACCOUNT,
        institution_code="014",
        account="936009140021948201",
    )
    assert qr_key != acct_key


def test_different_key_different_hash() -> None:
    inst = get_institution("ID", "014")
    h1, _ = normalize_account(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=inst,
        account_raw="8830192831",
        kms_key="key-v1",
    )
    h2, _ = normalize_account(
        country="ID",
        scheme=Scheme.BANK,
        entity_type=EntityType.BANK_ACCOUNT,
        institution=inst,
        account_raw="8830192831",
        kms_key="key-v2",
    )
    assert h1 != h2, "key rotation must change hashes (hash_version path)"


def test_leading_zeros_preserved() -> None:
    assert sanitize_account(" 000-123 ") == "000123"


def test_unsupported_bank_explicit_error() -> None:
    with pytest.raises(UnsupportedBankError):
        get_institution("ID", "999")


def test_length_validation() -> None:
    inst = get_institution("ID", "014")  # BCA: exactly 10
    with pytest.raises(NormalizationError, match="length"):
        normalize_account(
            country="ID",
            scheme=Scheme.BANK,
            entity_type=EntityType.BANK_ACCOUNT,
            institution=inst,
            account_raw="123",
            kms_key=KEY,
        )


def test_masking() -> None:
    assert mask_account("8830192831") == "883-****-831"
    assert mask_account("12345") == "12-****-45"
    assert mask_account("123") == "1-****"


def test_qr_identifier_mask_shows_tail() -> None:
    h, masked = normalize_qr_identifier(
        country="ID", scheme=Scheme.QRIS, nmid="936009140021948201", kms_key=KEY
    )
    assert len(h) == 64
    assert masked == "NMID ****8201"
