"""FastAPI application entrypoint — event-driven modular monolith (ADR-008)."""

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.system import router as system_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)  # /healthz, /protected-ping
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    return app


# fix forward ref for Depends used inside create_app body
from fastapi import Depends  # noqa: E402

app = create_app()
