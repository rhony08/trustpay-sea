"""AI provider registry.

`AI_PROVIDER` selects gcp | openrouter | mock. A configured provider that
cannot initialise (missing creds/SDK) transparently falls back to `mock` with a
warning, so dev/CI never need cloud credentials. Per-call redaction failures are
NOT retried against mock — they stay fail-closed in the worker.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.ai.errors import ProviderUnavailableError
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini import GeminiVertexProvider
from app.ai.providers.mock import MockProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.config import get_settings

log = logging.getLogger("trustpay.ai")


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    name = (settings.ai_provider or "mock").lower()
    try:
        if name == "gcp":
            return GeminiVertexProvider(settings)
        if name == "openrouter":
            return OpenRouterProvider(settings)
    except ProviderUnavailableError as exc:
        log.warning("AI provider %r unavailable (%s); falling back to mock", name, exc)
    return MockProvider()


def reset_ai_provider() -> None:
    get_ai_provider.cache_clear()


__all__ = ["AIProvider", "MockProvider", "get_ai_provider", "reset_ai_provider"]
