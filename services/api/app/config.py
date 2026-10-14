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

    # Evidence storage (Phase 2.2). Dev default is a local-disk shim; R2/S3
    # presigned uploads land behind the same Storage interface in Phase 7.
    evidence_storage_backend: str = "local"  # local | s3
    evidence_local_dir: str = "/tmp/trustpay-evidence"
    evidence_max_bytes: int = 8 * 1024 * 1024  # 8 MiB
    evidence_max_pixels: int = 25_000_000  # decompression-bomb guard
    evidence_public_base_url: str = "http://localhost:8000/media"  # cookieless domain in prod

    # Report quotas (Phase 2.1 / Doc 02 §5.2, §9)
    report_daily_quota_per_user: int = 20
    report_hourly_quota_per_entity: int = 5

    # Async worker cadence (Phase 2.3); scheduler safety-net poll interval.
    report_worker_interval_seconds: int = 20

    # AI summary cache (Phase 3.4): invalidated when the entity's signal version changes.
    ai_summary_cache_ttl_seconds: int = 3600

    # AI fail-closed test hook (Phase 2.3): force PII redaction to fail.
    ai_redaction_always_fail: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
