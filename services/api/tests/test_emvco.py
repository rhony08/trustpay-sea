"""EMVCo TLV parser tests (Phase 1.3) — shared fixtures from packages/test-vectors."""

from pathlib import Path

import pytest

from app.enums import Scheme
from app.resolver.emvco import (
    CRCError,
    EMVCoParseError,
    append_crc,
    crc16_ccitt,
    has_homoglyph_risk,
    parse_emvco,
)

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"


def _fixture(name: str) -> str:
    return (VECTORS / name).read_text().strip()


def test_parse_qris_fixture() -> None:
    parsed = parse_emvco(_fixture("qris_static.txt"))
    assert parsed.scheme == Scheme.QRIS
    assert parsed.nmid == "936009140021948201"
    assert parsed.merchant_name == "CV ELEKTRONIK JAYA MURAH"
    assert parsed.merchant_city == "JAKARTA"
    assert parsed.country == "ID"
    assert parsed.currency == "360"
    assert parsed.mcc == "5732"
    assert parsed.point_of_initiation == "STATIC"
    assert parsed.crc_valid


def test_parse_duitnow_fixture() -> None:
    parsed = parse_emvco(_fixture("duitnow_static.txt"))
    assert parsed.scheme == Scheme.DUITNOW
    assert parsed.country == "MY"
    assert parsed.merchant_name == "KEDAI MAKAN"


def test_parse_promptpay_fixture() -> None:
    parsed = parse_emvco(_fixture("promptpay_static.txt"))
    assert parsed.scheme == Scheme.PROMPTPAY
    assert parsed.nmid == "0000012345678"
    assert parsed.country == "TH"


def test_bad_crc_rejected() -> None:
    good = _fixture("qris_static.txt")
    corrupted = good[:-4] + ("0000" if good[-4:] != "0000" else "1111")
    with pytest.raises(CRCError, match="CRC mismatch"):
        parse_emvco(corrupted)


def test_truncated_tlv_rejected() -> None:
    with pytest.raises(EMVCoParseError):
        parse_emvco("00020101021226610014ID.CO.QRIS.WWW")


def test_unknown_gpi_rejected() -> None:
    body = "000201" + "010211" + "2620" + "0016EVIL.EXAMPLE.WWW" + "0102ab" + "5802ID" + "6304"
    with pytest.raises(EMVCoParseError, match="GPI"):
        parse_emvco(append_crc(body))


def test_payload_length_cap() -> None:
    with pytest.raises(EMVCoParseError, match="exceeds"):
        parse_emvco("0" * 600)


def test_crc16_known_value() -> None:
    # CRC-16/CCITT-FALSE("123456789") = 0x29B1
    assert crc16_ccitt("123456789") == "29B1"


def test_homoglyph_detector() -> None:
    assert has_homoglyph_risk("СV ELEKTRONIK")  # Cyrillic С
    assert has_homoglyph_risk("CV\u200bELEKTRONIK")  # zero-width space
    assert not has_homoglyph_risk("CV ELEKTRONIK")
    assert not has_homoglyph_risk(None)
