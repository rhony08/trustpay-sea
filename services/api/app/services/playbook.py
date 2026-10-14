"""Scam Playbook library (Phase 3B.10) — content keyed by the canonical taxonomy.

The taxonomy is the single source of truth; every category renders a playbook.
"""

from __future__ import annotations

from app.enums import ReportCategory

_PLAYBOOK: dict[ReportCategory, dict] = {
    ReportCategory.ONLINE_SHOP_GHOSTING: {
        "title": "Online shop ghosting",
        "summary": "A seller takes payment then disappears or never ships.",
        "red_flags": [
            "Prices far below market",
            "New account, few reviews",
            "Pushes off-platform chat",
        ],
        "checklist": [
            "Check the account on TrustPay",
            "Pay via protected methods",
            "Keep screenshots",
        ],
    },
    ReportCategory.FAKE_JOB: {
        "title": "Fake job offer",
        "summary": "A 'recruiter' asks for fees or documents for a job that doesn't exist.",
        "red_flags": [
            "Upfront fee for training/visa",
            "Interview only via chat",
            "Too-good salary",
        ],
        "checklist": ["Never pay to get a job", "Verify the company domain", "Report the account"],
    },
    ReportCategory.INVESTMENT_PIG_BUTCHERING: {
        "title": "Investment / pig butchering",
        "summary": "Long-con 'investment' platforms that show fake profits then block withdrawals.",
        "red_flags": [
            "Guaranteed returns",
            "Deposit more to withdraw",
            "Romance + investment combo",
        ],
        "checklist": [
            "Check platform licensing",
            "Never send to personal accounts",
            "Stop and verify",
        ],
    },
    ReportCategory.PHISHING_PRETEXTING: {
        "title": "Phishing / pretexting",
        "summary": "Messages impersonating banks/delivery ask you to click or share OTPs.",
        "red_flags": ["Urgent 'account suspended'", "Shortened links", "Requests for OTP/PIN"],
        "checklist": ["Banks never ask for OTP", "Open the app directly", "Report the sender"],
    },
    ReportCategory.IMPERSONATION: {
        "title": "Impersonation",
        "summary": "Scammers pose as family, officials, or brands to request money.",
        "red_flags": [
            "New number claiming to be a contact",
            "Urgency and secrecy",
            "Unusual payment method",
        ],
        "checklist": [
            "Call back on a known number",
            "Ask a verification question",
            "Check the account",
        ],
    },
    ReportCategory.UNAUTHORIZED_LENDING_PINJOL: {
        "title": "Illegal lending (pinjol)",
        "summary": "Unlicensed lenders with predatory terms and abusive collection.",
        "red_flags": ["No OJK license", "Access to your contacts", "Extreme interest"],
        "checklist": ["Verify the lender's license", "Never share contacts", "Report harassment"],
    },
    ReportCategory.NO_DELIVERY_GOODS: {
        "title": "Paid but no delivery",
        "summary": "Goods are paid for but never delivered, or stuck indefinitely.",
        "red_flags": ["Tracking never updates", "Excuses after payment", "Blocks after review"],
        "checklist": ["Check the account", "Pay on delivery when possible", "File with evidence"],
    },
    ReportCategory.EVENT_TICKET_FRAUD: {
        "title": "Event ticket fraud",
        "summary": "Fake or duplicate concert/event tickets sold via social media.",
        "red_flags": ["Urgency 'last ticket'", "No verified transfer", "Price above face value"],
        "checklist": ["Buy from official channels", "Verify the account", "Meet to transfer"],
    },
    ReportCategory.OTHER: {
        "title": "Other payment fraud",
        "summary": "Fraud that doesn't fit the common patterns.",
        "red_flags": ["Any unusual request for money", "Pressure to act fast"],
        "checklist": ["Stop and verify", "Check the account on TrustPay", "Keep evidence"],
    },
}


def list_playbooks() -> list[dict]:
    return [{"category": cat.value, **entry} for cat, entry in _PLAYBOOK.items()]


def get_playbook(category: str) -> dict | None:
    for cat, entry in _PLAYBOOK.items():
        if cat.value == category.upper():
            return {"category": cat.value, **entry}
    return None
