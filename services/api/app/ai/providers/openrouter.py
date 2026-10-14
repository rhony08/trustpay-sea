"""OpenRouter provider — OpenAI-compatible gateway to Gemini (and others).

Alternative to direct GCP. Same structured-output contract; JSON is requested
via `response_format` and parsed defensively (fences tolerated).
"""

from __future__ import annotations

import base64
from typing import Any

from app.ai.errors import ProviderUnavailableError
from app.ai.prompts import extract_json
from app.ai.providers.base import StructuredAIProvider
from app.config import Settings


class OpenRouterProvider(StructuredAIProvider):
    name = "openrouter"

    def __init__(self, settings: Settings) -> None:
        if not settings.openrouter_api_key:
            raise ProviderUnavailableError("OPENROUTER_API_KEY is not configured")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderUnavailableError("openai SDK is not installed") from exc
        self._client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            default_headers={"X-Title": settings.openrouter_app_name},
        )
        self._model = settings.openrouter_model

    async def _chat_json(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        return extract_json(response.choices[0].message.content or "")

    async def _vision_json(self, prompt: str, image: bytes, mime: str) -> dict[str, Any]:
        encoded = base64.b64encode(image).decode()
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
            ],
        }
        return await self._chat_json([message])

    async def _text_json(self, prompt: str) -> dict[str, Any]:
        return await self._chat_json([{"role": "user", "content": prompt}])
