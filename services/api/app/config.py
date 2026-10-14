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

    # CORS (comma-separated origins). Same-origin deploys behind nginx need only their own URL.
    cors_allow_origins: str = "http://localhost:3000"

    # Scheduler placeholder (Phase 0.5)
    scheduler_enabled: bool = True

    # Optional integrations (mock-first, ADR-012)
    gemini_api_key: str | None = None
    factcheck_api_key: str | None = None

    # --- Malaysia gov checker: PDRM Semak Mule (Phase G-MY) ---
    # Env-only secret — never commit the key. Checker is disabled when unset.
    semakmule_api_key: str | None = None
    semakmule_base_url: str = "https://semakmule.rmp.gov.my/api/mule/get_search_data.php"
    semakmule_timeout_seconds: float = 8.0
    # PDRM's chain is sometimes incomplete; keep True and mount a full CA bundle.
    semakmule_verify_tls: bool = True

    # --- AI provider (Phase 2/3 real model wiring) ---
    # mock (default, no key) | gcp (Vertex AI via ADC) | openrouter (OpenAI-compatible).
    # An unavailable/unconfigured provider transparently falls back to mock;
    # redaction stays fail-closed regardless of provider.
    ai_provider: str = "mock"
    # GCP / Vertex AI (preferred in the GCP deploy; uses Application Default Credentials)
    gcp_project: str | None = None
    gcp_location: str = "asia-southeast1"  # region-pin (Doc 02 §9.6)
    gcp_vision_model: str = "gemini-2.0-flash"
    gcp_text_model: str = "gemini-2.0-flash"
    # OpenRouter (alternative; OpenAI-compatible gateway)
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.0-flash-001"
    openrouter_app_name: str = "TrustPay SEA"

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

    # Public screen API keys + anti-probing (Phase 9 / docs/09)
    api_key_prefix: str = "tpk_live_"
    screen_visitor_daily_limit: int = 20  # keyless, per IP
    screen_demo_daily_limit: int = 100
    screen_partner_daily_limit: int = 1000
    screen_probe_visitor_distinct_per_hour: int = 50
    screen_probe_key_distinct_per_hour: int = 500

    # Async worker cadence (Phase 2.3); scheduler safety-net poll interval.
    report_worker_interval_seconds: int = 20

    # AI summary cache (Phase 3.4): invalidated when the entity's signal version changes.
    ai_summary_cache_ttl_seconds: int = 3600

    # Community engagement (Phase 3B)
    receipt_signing_key: str = "dev-only-insecure-receipt-key"
    quiz_pass_threshold: int = 2  # correct answers out of 3 for Anti-Scam Aware
    flag_rate_per_hour: int = 10  # per-user review-flag cap (Phase 4.2)

    # Data retention (Phase 10 / docs/10). Original evidence purged and report
    # bodies tombstoned after N days post-publication; legal hold + dispute freeze exempt.
    retention_evidence_days: int = 90
    retention_dry_run: bool = True  # safe default — logs candidates without deleting

    # AI fail-closed test hook (Phase 2.3): force PII redaction to fail.
    ai_redaction_always_fail: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
