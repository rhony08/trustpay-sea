"""Mock provider — the dev/test default (no API key required, ADR-012).

Wraps the local heuristic primitives so behaviour is identical to the original
mock-first pipeline.
"""

from __future__ import annotations

from app.ai import forensics, nlp, vision


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
