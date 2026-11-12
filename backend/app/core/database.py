from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base SQLAlchemy 2.x ORM model with consistent constraint naming."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database operation is requested without DATABASE_URL configured."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_async_database_url(database_url: str) -> str:
    """Normalize synchronous PostgreSQL/SQLite URLs into async SQLAlchemy driver URLs."""
    url = database_url.strip()
    if not url:
        return ""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://") :]
    if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        return "sqlite+aiosqlite:///" + url[len("sqlite:///") :]
    if url == "sqlite:///:memory:":
        return "sqlite+aiosqlite:///:memory:"
    return url


def normalize_sync_database_url(database_url: str) -> str:
    """Normalize async PostgreSQL/SQLite URLs into synchronous URLs for Alembic."""
    url = database_url.strip()
    if not url:
        return ""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("sqlite+aiosqlite:///"):
        return "sqlite:///" + url[len("sqlite+aiosqlite:///") :]
    return url


def create_engine_from_url(database_url: str, debug: bool = False) -> AsyncEngine:
    """Create an AsyncEngine with appropriate driver/pool configuration."""
    async_url = normalize_async_database_url(database_url)
    kwargs: dict[str, Any] = {
        "echo": debug,
        "future": True,
    }

    if async_url.startswith("sqlite+aiosqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in async_url:
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 300
        kwargs["pool_timeout"] = 30

    return create_async_engine(async_url, **kwargs)


def init_db(settings: Settings | None = None) -> AsyncEngine | None:
    """Initialize global AsyncEngine and session factory if DATABASE_URL is configured."""
    global _engine, _session_factory
    cfg = settings or get_settings()

    if not cfg.is_database_configured:
        _engine = None
        _session_factory = None
        logger.warning("database_not_configured", message="DATABASE_URL is not set")
        return None

    async_url = normalize_async_database_url(cfg.database_url)
    if cfg.app_env == "production" and async_url.startswith("sqlite"):
        raise DatabaseNotConfiguredError(
            "SQLite is not allowed when APP_ENV is 'production'. Configure PostgreSQL."
        )

    _engine = create_engine_from_url(cfg.database_url, debug=cfg.debug)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _engine


def set_db_engine(engine: AsyncEngine | None) -> None:
    """Override the active database engine and session factory (for tests)."""
    global _engine, _session_factory
    _engine = engine
    if engine is None:
        _session_factory = None
    else:
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )


def get_engine() -> AsyncEngine | None:
    """Return active AsyncEngine if initialized."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return active async_sessionmaker or raise DatabaseNotConfiguredError."""
    if _session_factory is None:
        settings = get_settings()
        if settings.is_database_configured:
            init_db(settings)
    if _session_factory is None:
        raise DatabaseNotConfiguredError(
            "Database is not configured. Set DATABASE_URL to enable persistence."
        )
    return _session_factory


async def close_db() -> None:
    """Dispose active SQLAlchemy engine connections cleanly."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional AsyncSession."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_health() -> tuple[str, str]:
    """Check live database connectivity without exposing credentials."""
    settings = get_settings()
    if not settings.is_database_configured and _engine is None:
        return "NOT_CONFIGURED", "DATABASE_URL is not configured."

    engine = _engine
    if engine is None and settings.is_database_configured:
        engine = init_db(settings)

    if engine is None:
        return "NOT_CONFIGURED", "Database engine is not initialized."

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "HEALTHY", "Database connection verified."
    except Exception as exc:
        logger.error("database_health_check_failed", error=str(exc))
        return "UNHEALTHY", "Database connectivity check failed."

