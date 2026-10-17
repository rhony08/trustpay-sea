"""Bank / institution directory (Phase 1.1).

Covers the six target markets (ID, MY, TH, SG, VN, PH). The canonical data
lives in ``app/data/banks/*.json`` — one file per country — and is the single
source of truth for both the resolver (canonical code used in the KMS-keyed
HMAC) and the ``banks`` DB table (seeded via ``app.seeds.seed_banks``), so the
reporting UI can only ever pick a controlled institution, never free text.

G-8: real bank code maps are demo-grade; licensing review is pending for
production. Institutions not in this directory must produce an explicit
"unsupported bank" error — never a silent pass-through.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "banks"

# Fallback account-number length when a bank has no published rule. Deliberately
# wide to avoid false rejections; per-bank overrides live in the JSON.
LENGTH_FALLBACKS: dict[str, tuple[int, int]] = {
    "ID": (6, 20),
    "MY": (6, 20),
    "TH": (10, 15),
    "SG": (6, 20),
    "VN": (6, 19),
    "PH": (6, 20),
}
_DEFAULT_LENGTH = (6, 20)


class UnsupportedBankError(Exception):
    def __init__(self, country: str | None, code: str) -> None:
        self.country = country
        self.code = code
        where = f"{country}:" if country else ""
        super().__init__(f"unsupported bank: {where}{code}")


class AmbiguousBankError(Exception):
    """A bank code that exists in more than one country (country required)."""

    def __init__(self, code: str, countries: list[str]) -> None:
        self.code = code
        self.countries = countries
        super().__init__(
            f"bank code {code!r} exists in multiple countries ({', '.join(countries)}); "
            "specify the country"
        )


@dataclass(frozen=True)
class Institution:
    country: str
    code: str  # local bank code / short code
    name: str
    bic: str | None
    min_length: int
    max_length: int
    bank_type: str | None = None  # COMMERCIAL | E_WALLET | ... (from the reference)


@lru_cache(maxsize=1)
def load_bank_records() -> tuple[dict, ...]:
    """All reference records, ordered by country file then declaration order."""
    records: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    return tuple(records)


def _resolve_length(record: dict) -> tuple[int, int]:
    fallback = LENGTH_FALLBACKS.get(record["country_code"], _DEFAULT_LENGTH)
    lo = record.get("min_length") or fallback[0]
    hi = record.get("max_length") or fallback[1]
    return int(lo), int(hi)


def _build_directory() -> dict[tuple[str, str], Institution]:
    directory: dict[tuple[str, str], Institution] = {}
    for record in load_bank_records():
        country = record["country_code"].upper()
        code = record["code"].upper()
        min_len, max_len = _resolve_length(record)
        directory[(country, code)] = Institution(
            country=country,
            code=record["code"],
            name=record["name"],
            bic=record.get("bic"),
            min_length=min_len,
            max_length=max_len,
            bank_type=record.get("bank_type"),
        )
    return directory


BANK_DIRECTORY: dict[tuple[str, str], Institution] = _build_directory()

SUPPORTED_COUNTRIES = ("ID", "MY", "TH", "SG", "VN", "PH")


def get_institution(country: str, code: str) -> Institution:
    inst = BANK_DIRECTORY.get((country.upper(), code.upper()))
    if inst is None:
        raise UnsupportedBankError(country, code)
    return inst


def institutions_by_code(code: str) -> list[Institution]:
    """All institutions matching a code across every country (codes aren't global)."""
    code_u = code.upper()
    return [inst for (_, c), inst in BANK_DIRECTORY.items() if c == code_u]


def resolve_institution(code: str, country: str | None = None) -> Institution:
    """Resolve an institution by code, with or without a country.

    - country given → exact (country, code) lookup.
    - country omitted → resolve by code alone; if the code is unique it wins,
      otherwise AmbiguousBankError tells the caller which countries exist.
    """
    if country:
        return get_institution(country, code)
    matches = institutions_by_code(code)
    if not matches:
        raise UnsupportedBankError(None, code)
    if len(matches) > 1:
        raise AmbiguousBankError(code, sorted(m.country for m in matches))
    return matches[0]


def institutions_for_country(country: str) -> list[Institution]:
    return [i for (c, _), i in BANK_DIRECTORY.items() if c == country.upper()]
