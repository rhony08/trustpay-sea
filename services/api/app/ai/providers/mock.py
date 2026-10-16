"""Mock provider — the dev/test default (no API key required, ADR-012).

Wraps the local heuristic primitives so behaviour is identical to the original
mock-first pipeline.
"""

from __future__ import annotations

import re

from app.ai import forensics, nlp, vision

_ACCOUNT_RE = re.compile(r"\b\d{8,20}\b")
_PHONE_RE = re.compile(r"(?:\+?62|0)8[0-9\-\s]{6,14}\d")
_IDENTITY_RE = re.compile(
    r"(?:admin|atas nama|nama saya|i am|this is|saya)\s+([A-Z][A-Za-z.'-]{2,40})", re.I
)


class MockProvider:
    name = "mock"

    async def redact_image(self, data: bytes) -> bytes:
        return vision.redact_image(data)

    async def ocr_slip(self, data: bytes) -> dict:
        return forensics.ocr_slip(data)

    async def detect_tampering(self, data: bytes) -> tuple[bool, dict]:
        return forensics.detect_tampering(data)

    async def classify_typology(self, text: str) -> tuple[str, float]:
        return nlp.classify_typology(text)

    async def extract_entities(self, text: str) -> dict:
        return nlp.extract_entities(text)

    async def judge_deal(self, text: str) -> dict:
        from app.services.safety_tools import check_too_good_to_be_true

        return check_too_good_to_be_true(text)

    async def analyze_message(self, text: str) -> dict:
        from app.services.safety_tools import check_too_good_to_be_true

        deal = check_too_good_to_be_true(text)
        signals = [{"code": s["code"], "label": s["tip"]} for s in deal["signals"]]
        count = len(signals)
        if count >= 3:
            risk_level = "CRITICAL"
        elif count == 2:
            risk_level = "HIGH"
        elif count == 1:
            risk_level = "CAUTION"
        else:
            risk_level = "LOW"
        account_match = _ACCOUNT_RE.search(text)
        phone_match = _PHONE_RE.search(text)
        identity_match = _IDENTITY_RE.search(text)
        category, _confidence = nlp.classify_typology(text)
        if count:
            summary = (
                "This message shows classic scam pressure tactics. Do not send money or share "
                "credentials, and verify the recipient through an official channel."
            )
        else:
            summary = (
                "No obvious scam signals were found, but always verify the recipient before paying."
            )
        return {
            "risk_level": risk_level,
            "signals": signals,
            "extracted": {
                "account": account_match.group(0) if account_match else None,
                "phone": phone_match.group(0).strip() if phone_match else None,
                "claimed_identity": identity_match.group(1).strip() if identity_match else None,
            },
            "suggested_category": category,
            "summary": summary,
            "tips": deal["tips"],
            "engine": "mock",
        }
