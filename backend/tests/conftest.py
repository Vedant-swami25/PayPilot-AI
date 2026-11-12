from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# Ensure isolated test configuration before importing app modules
os.environ.setdefault("APP_ENV", "testing")
os.environ["DEBUG"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long-12345")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-characters-long-67890")
os.environ.setdefault("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")

from app.api.dependencies import reset_shared_clients  # noqa: E402
from app.core.config import clear_settings_cache, get_settings  # noqa: E402
from app.core.database import Base, set_db_engine  # noqa: E402
from app.core.observability import observability  # noqa: E402
from app.core.security import api_rate_limiter, auth_rate_limiter  # noqa: E402
from app.llm import reset_circuit_breakers  # noqa: E402
from app.services.exchange_rate import clear_exchange_rate_cache  # noqa: E402
from app.services.product_service import clear_product_cache  # noqa: E402
import app.models  # noqa: F401, E402 - register ORM tables
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure clean settings, caches, and rate limiter per test."""
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-characters-long-12345")
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-characters-long-67890"
    )
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.setenv("NVIDIA_MODEL", "")
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    monkeypatch.setenv("MISTRAL_MODEL", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_MODEL", "")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "")
    monkeypatch.setenv("CHANNEL3_API_KEY", "")
    monkeypatch.setenv("ENABLE_TEST_PRODUCT_FIXTURES", "false")
    monkeypatch.setenv("DATABASE_URL", "")
    clear_settings_cache()
    reset_shared_clients()
    auth_rate_limiter.reset()
    api_rate_limiter.reset()
    observability.reset()
    reset_circuit_breakers()
    clear_product_cache()
    clear_exchange_rate_cache()


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    set_db_engine(engine)
    try:
        yield engine
    finally:
        set_db_engine(None)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    from app.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncGenerator[httpx.AsyncClient, None]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        yield async_client


async def register_and_login(
    client: httpx.AsyncClient,
    *,
    name: str = "Test Buyer",
    email: str = "buyer@example.com",
    password: str = "StrongPass123!",
) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
