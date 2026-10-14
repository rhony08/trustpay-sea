"""TrustPay SEA API settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TrustPay SEA API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "dev"  # dev | test | prod
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://trustpay:trustpay@localhost:5432/trustpay"
    redis_url: str = "redis://localhost:6379/0"

    # Auth (RS256 pinned — reject none/alg-confusion, ADR-013/§9.2)
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str = "/run/secrets/jwt_private.pem"
    jwt_public_key_path: str = "/run/secrets/jwt_public.pem"
    access_token_ttl_seconds: int = 900  # 15 min
    refresh_token_ttl_seconds: int = 604800  # 7 days
    issuer: str = "trustpay-sea"
    audience: str = "trustpay-api"

    # Rate limiting (token bucket, ADR-007 / §9.5)
    rate_limit_enabled: bool = True
    rate_limit_capacity: int = 60
    rate_limit_refill_per_minute: int = 60

    # Scheduler placeholder (Phase 0.5)
    scheduler_enabled: bool = True

    # Optional integrations (mock-first, ADR-012)
    gemini_api_key: str | None = None
    factcheck_api_key: str | None = None

    # Account hashing (ADR-002/013). MVP: key from env stands in for KMS/HSM;
    # real KMS wiring lands in Phase 7 hardening. hash_version on every row
    # makes rotation a re-encrypt, not a re-collect.
    account_hmac_key: str = "dev-only-insecure-key-change-me"
    account_hash_version: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
