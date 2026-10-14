"""Security-awareness tools (Phase 4B.2/4B.4/4B.5): scam heuristics, hotlines, recovery."""

from __future__ import annotations

import re

# --- 4B.2 Too-good-to-be-true deal checker ---------------------------------

_SIGNALS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"guarantee|pasti untung|dijamin|no risk|risk[- ]free", re.I),
        "guaranteed_returns",
        "Real investments are never guaranteed. Treat 'guaranteed profit' as a scam.",
    ),
    (
        re.compile(r"double your money|gandakan uang|100%\s*(profit|return)", re.I),
        "implausible_returns",
        "No legitimate scheme doubles your money quickly.",
    ),
    (
        re.compile(r"(\d{2,3})\s*%\s*(off|discount|lebih murah)", re.I),
        "extreme_discount",
        "Extreme discounts are often bait — pay via protected methods only.",
    ),
    (
        re.compile(r"urgent|hurry|today only|last chance|segera|cepat|terbatas", re.I),
        "urgency",
        "Pressure to act fast is a classic manipulation tactic. Slow down.",
    ),
    (
        re.compile(r"\b(free|gratis)\b.*\b(money|money|iphone|gold|hadiah)\b", re.I),
        "free_bait",
        "Free high-value giveaways are bait for fees or data.",
    ),
    (
        re.compile(r"winner|menang|lottery|undian|you.?ve won", re.I),
        "fake_prize",
        "You can't win a lottery you never entered.",
    ),
    (
        re.compile(r"deposit|top ?up|join now|klik link|click (this|here)", re.I),
        "deposit_pressure",
        "Being pushed to deposit or click a link is a red flag.",
    ),
]
_PERCENT_RE = re.compile(r"(\d{2,3})\s*%", re.I)


def check_too_good_to_be_true(text: str) -> dict:
    signals: list[dict] = []
    for pattern, code, tip in _SIGNALS:
        if pattern.search(text):
            signals.append({"code": code, "tip": tip})
    for match in _PERCENT_RE.findall(text):
        if int(match) >= 70:
            code = "extreme_discount"
            if not any(s["code"] == code for s in signals):
                signals.append(
                    {"code": code, "tip": "Discounts of 70%+ are usually fake. Verify the seller."}
                )
    score = min(100, len(signals) * 25)
    return {
        "suspicious": len(signals) >= 1,
        "score": score,
        "signals": signals,
        "tips": [s["tip"] for s in signals],
    }


# --- 4B.4 Geo-aware SOS hotlines -------------------------------------------

_HOTLINES: dict[str, list[dict]] = {
    "ID": [
        {"name": "Police emergency", "number": "110"},
        {"name": "OJK consumer hotline", "number": "157"},
        {"name": "cekrekening.id", "url": "https://cekrekening.id"},
    ],
    "MY": [
        {"name": "NSRC Scam Response", "number": "997"},
        {"name": "Semak Mule", "url": "https://semakmule.rmp.gov.my"},
    ],
    "SG": [
        {"name": "Police emergency", "number": "999"},
        {"name": "Anti-Scam Command", "number": "1800-255-0000"},
        {"name": "ScamShield", "url": "https://www.scamshield.gov.sg"},
    ],
    "TH": [
        {"name": "AOC 1441", "number": "1441"},
        {"name": "Police emergency", "number": "191"},
    ],
    "VN": [
        {"name": "Police emergency", "number": "113"},
        {"name": "NCSC", "url": "https://canhbao.ncsc.gov.vn"},
    ],
    "PH": [
        {"name": "Emergency", "number": "911"},
        {"name": "IACAT", "url": "https://www.iacat.gov.ph"},
    ],
}


def hotlines_for(country: str) -> list[dict]:
    return _HOTLINES.get(country.upper(), [])


# --- 4B.5 "I just got scammed" recovery wizard ------------------------------

_REFERRAL = {
    "ID": {"name": "cekrekening.id report", "url": "https://cekrekening.id"},
    "MY": {"name": "Semak Mule / NSRC report", "url": "https://semakmule.rmp.gov.my"},
    "SG": {"name": "SPF Anti-Scam Command report", "url": "https://www.police.gov.sg"},
    "TH": {"name": "AOC 1441 report", "url": "https://www.thaipoliceonline.com"},
    "VN": {"name": "NCSC report", "url": "https://canhbao.ncsc.gov.vn"},
    "PH": {"name": "IACAT report", "url": "https://www.iacat.gov.ph"},
}


def recovery_plan(country: str, bank: str | None = None) -> dict:
    return {
        "country": country.upper(),
        "immediate_steps": [
            "Call your bank's hotline and ask them to freeze the account / block the transfer.",
            "Change your banking passwords and disable any app tokens the scammer may see.",
            "Do not send any further payments, even if asked to 'unlock' the money.",
        ],
        "freeze_steps": [
            "Open your banking app → Card/Account settings → Freeze or block the card.",
            "If you transferred recently, request a recall/chargeback with the reference ID.",
            "Ask the bank to flag the recipient account as reported-for-fraud.",
        ],
        "referral": _REFERRAL.get(
            country.upper(), {"name": "Local police", "url": "https://www.interpol.int"}
        ),
        "dossier_hint": "Generate a Diligence Receipt and attach your transfer slip as evidence.",
        "bank": bank,
    }
