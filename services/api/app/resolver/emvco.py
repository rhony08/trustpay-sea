"""EMVCo QR TLV parser with CRC-16 validation (Phase 1.3).

Supports QRIS (ID), DuitNow (MY), PromptPay (TH), PayNow/SGQR (SG),
VietQR (VN), QR Ph (PH). Hybrid model per ADR-001: the server re-parses and
validates whatever the client decoded — the server parse is authoritative.
"""

import re
from dataclasses import dataclass, field

from app.enums import Scheme

MAX_PAYLOAD_LENGTH = 512  # DoS guard (Doc 02 §9.5)
MAX_NESTING_DEPTH = 4


class EMVCoParseError(Exception):
    pass


class CRCError(EMVCoParseError):
    pass


# reverse-domain GPI (subtag 00 of tags 26-51) → scheme
_GPI_TO_SCHEME: dict[str, Scheme] = {
    "ID.CO.QRIS.WWW": Scheme.QRIS,
    "MY.DUITNOW.WWW": Scheme.DUITNOW,
    "TH.OR.PAYMENT.PROMPTPAY": Scheme.PROMPTPAY,
    "SG.PAYNOW": Scheme.PAYNOW,
    "VN.VNPAYQR": Scheme.VIETQR,
    "VN.VNPAYQR.VNPAY": Scheme.VIETQR,
    "PH.EPCQRPH": Scheme.QRPH,
    "PH.QRPH": Scheme.QRPH,
}

_CURRENCY_BY_COUNTRY = {
    "ID": "360",
    "MY": "458",
    "TH": "764",
    "SG": "702",
    "VN": "704",
    "PH": "608",
}


@dataclass(frozen=True)
class TLVField:
    tag: str
    value: str
    subtags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedQR:
    scheme: Scheme
    point_of_initiation: str  # STATIC | DYNAMIC
    merchant_account_info: dict[str, str]
    gpi: str | None
    nmid: str | None
    mcc: str | None
    currency: str | None
    amount: str | None
    country: str | None
    merchant_name: str | None
    merchant_city: str | None
    additional_fields: dict[str, str]  # anything else, raw
    crc_valid: bool


def crc16_ccitt(data: str) -> str:
    """CRC-16/CCITT-FALSE over `data` exactly as given (EMVCo QR: the input is
    the payload up to and including the tag-63 length header '6304')."""
    raw = data.encode("ascii")
    crc = 0xFFFF
    for byte in raw:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def append_crc(payload_without_crc: str) -> str:
    """payload ending in '6304' + its CRC value."""
    return payload_without_crc + crc16_ccitt(payload_without_crc)


def parse_tlv(payload: str, *, _depth: int = 0) -> list[TLVField]:
    if _depth > MAX_NESTING_DEPTH:
        raise EMVCoParseError("TLV nesting too deep")
    fields: list[TLVField] = []
    i = 0
    while i < len(payload):
        if i + 4 > len(payload):
            raise EMVCoParseError(f"truncated TLV header at offset {i}")
        tag = payload[i : i + 2]
        if not tag.isdigit():
            raise EMVCoParseError(f"non-numeric tag at offset {i}")
        try:
            length = int(payload[i + 2 : i + 4])
        except ValueError as exc:
            raise EMVCoParseError(f"bad length at offset {i}") from exc
        start = i + 4
        end = start + length
        if end > len(payload):
            raise EMVCoParseError(f"value overruns payload at tag {tag}")
        value = payload[start:end]
        subtags: dict[str, str] = {}
        if tag in {str(t) for t in range(26, 52)} or tag in {"00", "01"} and _depth > 0:
            try:
                for sub in parse_tlv(value, _depth=_depth + 1):
                    subtags[sub.tag] = sub.value
            except EMVCoParseError:
                subtags = {}  # not a nested TLV container — keep raw
        fields.append(TLVField(tag=tag, value=value, subtags=subtags))
        i = end
    return fields


def _find(fields: list[TLVField], tag: str) -> TLVField | None:
    return next((f for f in fields if f.tag == tag), None)


def detect_scheme_from_gpi(gpi: str) -> Scheme | None:
    return _GPI_TO_SCHEME.get(gpi.upper())


def parse_emvco(payload: str) -> ParsedQR:
    if not payload or not payload.isascii():
        raise EMVCoParseError("payload must be non-empty ASCII EMVCo TLV")
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise EMVCoParseError(f"payload exceeds {MAX_PAYLOAD_LENGTH} chars")
    if not payload.startswith("000201"):
        raise EMVCoParseError("missing Payload Format Indicator (tag 00 = '01')")

    fields = parse_tlv(payload)

    crc_field = _find(fields, "63")
    if crc_field is None or len(crc_field.value) != 4:
        raise CRCError("missing or malformed CRC (tag 63)")
    expected = crc16_ccitt(payload[:-4])
    if crc_field.value.upper() != expected:
        raise CRCError(f"CRC mismatch: got {crc_field.value}, expected {expected}")

    # merchant account info: first populated tag in 26..51
    mai: dict[str, str] = {}
    gpi: str | None = None
    nmid: str | None = None
    for f in fields:
        if f.tag.isdigit() and 26 <= int(f.tag) <= 51 and f.subtags:
            mai = dict(f.subtags)
            gpi = f.subtags.get("00")
            nmid = f.subtags.get("01")
            break

    scheme = detect_scheme_from_gpi(gpi) if gpi else None
    if scheme is None:
        raise EMVCoParseError(f"unrecognized or missing GPI: {gpi!r}")

    poi_field = _find(fields, "01")
    poi_raw = poi_field.value if poi_field else "11"
    point_of_initiation = "DYNAMIC" if poi_raw == "12" else "STATIC"

    def val(tag: str) -> str | None:
        f = _find(fields, tag)
        return f.value if f else None

    known = {"00", "01", *[str(t) for t in range(26, 52)], "52", "53", "54", "58", "59", "60", "63"}
    additional = {f.tag: f.value for f in fields if f.tag not in known}

    country = val("58")
    currency = val("53")
    if country and currency and _CURRENCY_BY_COUNTRY.get(country.upper()) != currency:
        # not fatal (some cross-border QRs), but worth surfacing to the parser caller
        pass

    return ParsedQR(
        scheme=scheme,
        point_of_initiation=point_of_initiation,
        merchant_account_info=mai,
        gpi=gpi,
        nmid=nmid,
        mcc=val("52"),
        currency=currency,
        amount=val("54"),
        country=country.upper() if country else None,
        merchant_name=val("59"),
        merchant_city=val("60"),
        additional_fields=additional,
        crc_valid=True,
    )


_NAME_LOOKALIKE_RE = re.compile(
    "[\u0400-\u04ff]"  # any Cyrillic — catches Latin lookalikes А В С Е О Р Н Х etc.
    "|[\u200b\u200c\u200d\ufeff]"  # zero-width / BOM
    "|[\uff21-\uff5e]"  # fullwidth Latin (NFKC folds them to ASCII)
)


def has_homoglyph_risk(name: str | None) -> bool:
    """H12: unicode normalization + lookalike-name detector."""
    if not name:
        return False
    import unicodedata

    normalized = unicodedata.normalize("NFKC", name)
    if normalized != name:
        return True
    return bool(_NAME_LOOKALIKE_RE.search(name))
