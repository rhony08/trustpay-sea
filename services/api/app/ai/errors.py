"""AI layer errors — shared so the worker can fail-closed on redaction."""


class AIError(Exception):
    pass


class RedactionError(AIError):
    """PII redaction failed. The worker MUST NOT publish unredacted evidence."""


class ProviderUnavailableError(AIError):
    """Configured provider could not initialise (missing creds/SDK) → fall back to mock."""
