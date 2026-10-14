"""NLP scam typology + NER extraction (Phase 2.6, Doc 02 §4.3).

Mock-first and prompt-injection-safe **by construction**: this runs locally as a
keyword classifier, so untrusted report text can never become instructions. A
Gemini classifier can replace `classify_typology` later without changing the
contract — output always maps to the one canonical `ReportCategory` taxonomy.
"""

from __future__ import annotations

import re

from app.enums import ReportCategory

_KEYWORDS: dict[ReportCategory, tuple[str, ...]] = {
    ReportCategory.ONLINE_SHOP_GHOSTING: (
        "online shop",
        "instagram shop",
        "toko online",
        "shopee seller",
        "facebook marketplace",
        "ghosting",
        "not shipped",
        "seller disappeared",
    ),
    ReportCategory.FAKE_JOB: (
        "job",
        "hiring",
        "recruitment",
        "vacancy",
        "lowongan",
        "kerja",
        "interview fee",
        "part time job",
    ),
    ReportCategory.INVESTMENT_PIG_BUTCHERING: (
        "investment",
        "investasi",
        "crypto",
        "trading",
        "profit",
        "return",
        "forex",
        "keuntungan",
        "bot trading",
    ),
    ReportCategory.PHISHING_PRETEXTING: (
        "phishing",
        "otp",
        "link",
        "click here",
        "verify your",
        "verifikasi",
        "install apk",
        "apk",
        "login bank",
    ),
    ReportCategory.IMPERSONATION: (
        "impersonat",
        "pretending",
        "fake account",
        "palsu",
        "atas nama",
        "mengaku",
        "family member",
    ),
    ReportCategory.UNAUTHORIZED_LENDING_PINJOL: (
        "pinjol",
        "pinjaman",
        "lending",
        "loan",
        "debt collector",
        "bunga",
        "illegal loan",
    ),
    ReportCategory.NO_DELIVERY_GOODS: (
        "no delivery",
        "not delivered",
        "barang tidak sampai",
        "belum kirim",
        "never received",
        "shipping stuck",
    ),
    ReportCategory.EVENT_TICKET_FRAUD: (
        "ticket",
        "tiket",
        "concert",
        "konser",
        "event",
        "festival",
    ),
}

_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard instructions",
    "system prompt",
    "you are now",
    "forget everything",
    "developer mode",
)

_PHONE_RE = re.compile(r"(?:\+?62|0)8\d{7,11}")
_URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(?:rp|idr|rm|sgd|thb|vnd|php|\$)\s?[\d.,]{3,}", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{3,32}")


def classify_typology(text: str) -> tuple[str, float]:
    """Map free text to the canonical taxonomy. Returns (category, confidence)."""
    lowered = text.lower()
    best: ReportCategory = ReportCategory.OTHER
    best_hits = 0
    for category, keywords in _KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best, best_hits = category, hits
    if best_hits == 0:
        return ReportCategory.OTHER.value, 0.0
    return best.value, min(1.0, 0.5 + 0.25 * best_hits)


def looks_like_injection(text: str) -> bool:
    """Flag instruction-like text; the classifier ignores it regardless."""
    lowered = text.lower()
    return any(marker in lowered for marker in _INJECTION_MARKERS)


def extract_entities(text: str) -> dict:
    """NER with masking hints — raw PII is never surfaced publicly."""
    phones = _PHONE_RE.findall(text)
    urls = _URL_RE.findall(text)
    amounts = _AMOUNT_RE.findall(text)
    dates = _DATE_RE.findall(text)
    handles = _HANDLE_RE.findall(text)
    return {
        "phone_hints": [f"****{p[-4:]}" for p in phones],
        "url_hosts": [u.split("/")[2] if "//" in u else u.split("/")[0] for u in urls],
        "amount_hints": [a.strip() for a in amounts],
        "dates": dates,
        "handles": handles,
        "injection_suspected": looks_like_injection(text),
    }
