"""AI provider interface + a structured-output base class.

Capabilities mirror the mock primitives so the worker is provider-agnostic.
Real providers implement two primitives (`_vision_json`, `_text_json`) and
inherit the redaction/OCR/tamper/typology/NER logic, keeping validation,
masking and fail-closed behaviour in one place.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.ai import nlp
from app.ai.errors import RedactionError
from app.ai.prompts import (
    NER_PROMPT,
    OCR_PROMPT,
    PII_REGION_PROMPT,
    TAMPER_PROMPT,
    TYPOLOGY_PROMPT,
    draw_redaction,
    extract_json,
    mask_ner,
    valid_category,
)


@runtime_checkable
class AIProvider(Protocol):
    name: str

    async def redact_image(self, data: bytes) -> bytes: ...
    async def ocr_slip(self, data: bytes) -> dict: ...
    async def detect_tampering(self, data: bytes) -> tuple[bool, dict]: ...
    async def classify_typology(self, text: str) -> tuple[str, float]: ...
    async def extract_entities(self, text: str) -> dict: ...


class StructuredAIProvider:
    """Gemini/OpenRouter share this: model → JSON → validated domain objects."""

    name = "structured"

    async def _vision_json(self, prompt: str, image: bytes, mime: str) -> dict[str, Any]:
        raise NotImplementedError

    async def _text_json(self, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    async def redact_image(self, data: bytes) -> bytes:
        try:
            obj = await self._vision_json(PII_REGION_PROMPT, data, "image/jpeg")
        except Exception as exc:  # noqa: BLE001 — any failure must fail closed
            raise RedactionError(str(exc)) from exc
        return draw_redaction(data, obj.get("regions"))

    async def ocr_slip(self, data: bytes) -> dict:
        obj = await self._vision_json(OCR_PROMPT, data, "image/jpeg")
        keys = ("sender", "recipient", "ref_id", "time", "amount", "text")
        return {"engine": self.name, **{k: obj.get(k) for k in keys}}

    async def detect_tampering(self, data: bytes) -> tuple[bool, dict]:
        obj = await self._vision_json(TAMPER_PROMPT, data, "image/jpeg")
        return bool(obj.get("tampering_detected")), {
            "engine": self.name,
            "signals": obj.get("signals") or [],
        }

    async def classify_typology(self, text: str) -> tuple[str, float]:
        obj = await self._text_json(TYPOLOGY_PROMPT + text)
        try:
            confidence = float(obj.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        return valid_category(obj.get("category")), confidence

    async def extract_entities(self, text: str) -> dict:
        obj = await self._text_json(NER_PROMPT + text)
        return mask_ner(obj, injection_suspected=nlp.looks_like_injection(text))


__all__ = ["AIProvider", "StructuredAIProvider", "extract_json"]
