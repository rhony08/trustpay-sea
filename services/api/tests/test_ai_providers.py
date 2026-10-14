"""AI provider abstraction tests (GCP/OpenRouter selection, structured output).

No network: real providers are exercised through a fake `StructuredAIProvider`
subclass; registry fallback is verified with missing credentials.
"""

from pathlib import Path

import pytest

from app.ai.errors import RedactionError
from app.ai.prompts import draw_redaction, extract_json, valid_category
from app.ai.providers import get_ai_provider, reset_ai_provider
from app.ai.providers.base import StructuredAIProvider
from app.config import get_settings

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
PNG = (VECTORS / "qris_static.png").read_bytes()


@pytest.fixture(autouse=True)
def _reset_ai_caches():
    yield
    get_settings.cache_clear()
    reset_ai_provider()


class _FakeProvider(StructuredAIProvider):
    name = "fake"

    def __init__(self, *, vision: dict | None = None, text: dict | None = None, fail: bool = False):
        self._vision = vision or {}
        self._text = text or {}
        self._fail = fail

    async def _vision_json(self, prompt: str, image: bytes, mime: str) -> dict:
        if self._fail:
            raise RuntimeError("model unavailable")
        return self._vision

    async def _text_json(self, prompt: str) -> dict:
        if self._fail:
            raise RuntimeError("model unavailable")
        return self._text


def test_default_provider_is_mock() -> None:
    get_settings.cache_clear()
    reset_ai_provider()
    assert get_ai_provider().name == "mock"


def test_openrouter_without_key_falls_back_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    reset_ai_provider()
    assert get_ai_provider().name == "mock"


def test_gcp_without_project_falls_back_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "gcp")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    get_settings.cache_clear()
    reset_ai_provider()
    assert get_ai_provider().name == "mock"


def test_extract_json_tolerates_fences_and_rejects_garbage() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"b": 2} suffix') == {"b": 2}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_valid_category_constrains_to_taxonomy() -> None:
    assert valid_category("phishing_pretexting") == "PHISHING_PRETEXTING"
    assert valid_category("not_a_category") == "OTHER"


def test_draw_redaction_boxes_and_empty_fallback() -> None:
    boxed = draw_redaction(PNG, [{"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}])
    assert boxed[:3] == b"\xff\xd8\xff"
    fallback = draw_redaction(PNG, [])
    assert fallback[:3] == b"\xff\xd8\xff"


async def test_structured_provider_redaction_and_ner() -> None:
    provider = _FakeProvider(
        vision={"regions": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}]},
        text={
            "category": "PHISHING_PRETEXTING",
            "confidence": 0.8,
            "phone_numbers": ["+6281234567890"],
            "urls": ["https://scam.example/x"],
        },
    )
    assert (await provider.redact_image(PNG))[:3] == b"\xff\xd8\xff"

    category, confidence = await provider.classify_typology("otp link")
    assert category == "PHISHING_PRETEXTING"
    assert confidence == 0.8

    ner = await provider.extract_entities("call +6281234567890")
    assert ner["phone_hints"] == ["****7890"]
    assert ner["url_hosts"] == ["scam.example"]


async def test_structured_provider_redaction_fails_closed() -> None:
    with pytest.raises(RedactionError):
        await _FakeProvider(fail=True).redact_image(PNG)


async def test_structured_provider_ocr_shape() -> None:
    provider = _FakeProvider(vision={"sender": "A", "amount": "1500000", "ref_id": "X1"})
    result = await provider.ocr_slip(PNG)
    assert result["engine"] == "fake"
    assert result["amount"] == "1500000"
