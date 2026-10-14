"""Shared pytest fixtures — real Postgres + Redis (compose / CI services)."""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Test env must be set before app imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trustpay:trustpay@localhost:5432/trustpay_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "true")

from app.config import get_settings  # noqa: E402
from app.core.security import JWTService  # noqa: E402
from app.db import Base, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def jwt_keypair(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Ephemeral RS256 keypair for the test session."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key_dir = tmp_path_factory.mktemp("keys")
    priv, pub = key_dir / "priv.pem", key_dir / "pub.pem"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    settings = get_settings()
    get_settings.cache_clear()
    os.environ["JWT_PRIVATE_KEY_PATH"] = str(priv)
    os.environ["JWT_PUBLIC_KEY_PATH"] = str(pub)
    settings = get_settings()
    assert JWTService(settings)  # fails fast if keys unreadable


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    from app.main import app

    transport = ASGITransport(app=app)
    # app.state.redis only exists under lifespan; run it manually for ASGITransport
    async with (
        AsyncClient(transport=transport, base_url="http://test") as c,
        app.router.lifespan_context(app),
    ):
        yield c
