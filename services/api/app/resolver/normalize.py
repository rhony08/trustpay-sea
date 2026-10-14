"""Account normalization + KMS-keyed HMAC canonical index (Phase 1.2).

Doc 02 §2.1 algorithm:
  1. sanitize  = strip non-alphanumerics, preserve significant leading zeros
  2. institution = canonical code from the bank directory
  3. canonical_key = country:scheme:entity_type:institution:sanitize
  4. account_hash  = HMAC_SHA256(canonical_key, kms_key)   (hash_version per row)
  5. masked        = first3-****-last3

H11 collision guard: entity_type + scheme are IN the key, so a phone alias can
never collide with a bank account of the same digits, nor a QR NMID with a raw
account. Lookups are exact-match on the hash — no substring/ILIKE enumeration.
"""

import hashlib
import hmac
import re

from app.enums import EntityType, Scheme
from app.resolver.banks import Institution

_SANITIZE_RE = re.compile(r"[^0-9A-Za-z]")


class NormalizationError(Exception):
    pass


def sanitize_account(account_raw: str) -> str:
    """Strip formatting; keep alphanumeric core (incl. significant letters for
    wallet IDs like GOPAY/phone aliases)."""
    sanitized = _SANITIZE_RE.sub("", account_raw)
    if not sanitized:
        raise NormalizationError("account contains no alphanumeric characters")
    return sanitized


def validate_length(institution: Institution, sanitized: str) -> None:
    if not (institution.min_length <= len(sanitized) <= institution.max_length):
        raise NormalizationError(
            f"account length {len(sanitized)} outside allowed range "
            f"{institution.min_length}-{institution.max_length} for {institution.name}"
        )


def canonical_key(
    *,
    country: str,
    scheme: Scheme | str,
    entity_type: EntityType | str,
    institution_code: str | None,
    account: str,
) -> str:
    return ":".join(
        [
            country.upper(),
            str(scheme),
            str(entity_type),
            (institution_code or "").upper(),
            account,
        ]
    )


def hmac_hash(key_material: str, kms_key: str) -> str:
    return hmac.new(kms_key.encode(), key_material.encode(), hashlib.sha256).hexdigest()


def mask_account(sanitized: str) -> str:
    """first3-****-last3; degrade gracefully for short identifiers."""
    if len(sanitized) >= 8:
        return f"{sanitized[:3]}-****-{sanitized[-3:]}"
    if len(sanitized) >= 5:
        return f"{sanitized[:2]}-****-{sanitized[-2:]}"
    return f"{sanitized[:1]}-****"


def normalize_account(
    *,
    country: str,
    scheme: Scheme | str,
    entity_type: EntityType,
    institution: Institution,
    account_raw: str,
    kms_key: str,
) -> tuple[str, str]:
    """Returns (account_hash, account_masked)."""
    sanitized = sanitize_account(account_raw)
    validate_length(institution, sanitized)
    key = canonical_key(
        country=country,
        scheme=scheme,
        entity_type=entity_type,
        institution_code=institution.code,
        account=sanitized,
    )
    return hmac_hash(key, kms_key), mask_account(sanitized)


def normalize_qr_identifier(
    *,
    country: str,
    scheme: Scheme | str,
    nmid: str,
    kms_key: str,
) -> tuple[str, str]:
    """QR entities key on scheme:NMID (Doc 02 §2.2); masked shows NMID tail."""
    sanitized = sanitize_account(nmid)
    key = canonical_key(
        country=country,
        scheme=scheme,
        entity_type=EntityType.QR_CODE,
        institution_code=None,
        account=sanitized,
    )
    masked = f"NMID ****{sanitized[-4:]}" if len(sanitized) >= 4 else "NMID ****"
    return hmac_hash(key, kms_key), masked
