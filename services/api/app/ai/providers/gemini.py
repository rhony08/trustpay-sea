"""GCP / Vertex AI Gemini provider (uses Application Default Credentials).

Preferred for the GCP deploy: authenticates via the runtime service account /
Workload Identity, pins the SEA region, and requests JSON output. SDKs are
imported lazily so the app boots without them.
"""

from __future__ import annotations

from typing import Any

from app.ai.errors import ProviderUnavailableError
from app.ai.prompts import extract_json
from app.ai.providers.base import StructuredAIProvider
from app.config import Settings


class GeminiVertexProvider(StructuredAIProvider):
    name = "gcp"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcp_project:
            raise ProviderUnavailableError("GCP_PROJECT is not configured")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ProviderUnavailableError("google-genai is not installed") from exc
        self._genai = genai
        self._client = genai.Client(
            vertexai=True,
            project=settings.gcp_project,
            location=settings.gcp_location,
        )
        self._vision_model = settings.gcp_vision_model
        self._text_model = settings.gcp_text_model

    async def _generate(self, *, model: str, contents: Any) -> dict[str, Any]:
        from google.genai import types

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        return extract_json(response.text or "")

    async def _vision_json(self, prompt: str, image: bytes, mime: str) -> dict[str, Any]:
        from google.genai import types

        part = types.Part.from_bytes(data=image, mime_type=mime)
        return await self._generate(model=self._vision_model, contents=[part, prompt])

    async def _text_json(self, prompt: str) -> dict[str, Any]:
        return await self._generate(model=self._text_model, contents=prompt)
