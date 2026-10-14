"""FastAPI application entrypoint — event-driven modular monolith (ADR-008)."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.banks import router as banks_router
from app.api.community import router as community_router
from app.api.disputes import router as disputes_router
from app.api.entities import router as entities_router
from app.api.keys import router as keys_router
from app.api.moderation import router as moderation_router
from app.api.profile import router as profile_router
from app.api.reports import router as reports_router
from app.api.screen import router as screen_router
from app.api.system import router as system_router
from app.api.tools import router as tools_router
from app.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.jobs.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("trustpay")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    if settings.scheduler_enabled:
        start_scheduler()
    log.info("TrustPay API up (env=%s, version=%s)", settings.environment, settings.version)
    try:
        yield
    finally:
        shutdown_scheduler()
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        dependencies=[Depends(enforce_rate_limit)],  # noqa: F821 — see import below
    )
    # CORS for the first-party PWA (BFF/proxy preferred for prod keys, §9.5)
    allow_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)  # /healthz, /protected-ping
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(entities_router, prefix=settings.api_v1_prefix)
    app.include_router(banks_router, prefix=settings.api_v1_prefix)
    app.include_router(reports_router, prefix=settings.api_v1_prefix)
    app.include_router(profile_router, prefix=settings.api_v1_prefix)
    app.include_router(community_router, prefix=settings.api_v1_prefix)
    app.include_router(moderation_router, prefix=settings.api_v1_prefix)
    app.include_router(tools_router, prefix=settings.api_v1_prefix)
    app.include_router(disputes_router, prefix=settings.api_v1_prefix)
    app.include_router(admin_router, prefix=settings.api_v1_prefix)
    app.include_router(keys_router, prefix=settings.api_v1_prefix)
    app.include_router(screen_router, prefix=settings.api_v1_prefix)

    # Dev-only: serve redacted public evidence as static files. Production uses a
    # separate cookieless media domain (Doc 02 §9.1); quarantine is never mounted.
    if settings.evidence_storage_backend == "local":
        public_dir = Path(settings.evidence_local_dir) / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=public_dir), name="media")
    return app


# fix forward ref for Depends used inside create_app body
from fastapi import Depends  # noqa: E402

app = create_app()
