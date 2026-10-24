"""Database engine and session management."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Any, AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.errors import DatabaseUnavailableError

# Managed PostgreSQL providers hand out "postgres://" URLs, which SQLAlchemy
# treats as a distinct driver name, so accept it alongside the canonical ones.
_SUPPORTED_DRIVERS = {"postgres", "postgresql", "postgresql+asyncpg"}

# libpq-only query options that asyncpg does not understand. "sslmode" is the
# managed-provider spelling of asyncpg's "ssl" connect argument.
_QUERY_ALIASES = {"sslmode": "ssl"}


def normalize_database_url(url_str: str) -> URL:
    """Validate a PostgreSQL URL and rewrite it for the asyncpg driver."""
    url = make_url(url_str)
    if url.drivername not in _SUPPORTED_DRIVERS:
        raise DatabaseUnavailableError(
            message="DATABASE_URL must be a PostgreSQL connection URL.",
            hint="Use postgresql+asyncpg://user:pass@host:port/dbname.",
        )

    query: dict[str, Any] = {}
    for key, value in url.query.items():
        query[_QUERY_ALIASES.get(key, key)] = value

    return url.set(drivername="postgresql+asyncpg", query=query)


def get_database_url() -> str:
    """Retrieve and validate the PostgreSQL connection string."""
    url_str = os.getenv("DATABASE_URL")
    if not url_str:
        raise DatabaseUnavailableError(
            message="DATABASE_URL is required but not configured.",
            hint="Set DATABASE_URL in your environment or .env file.",
        )
    return normalize_database_url(url_str).render_as_string(hide_password=False)


def get_engine() -> AsyncEngine:
    """Create an asynchronous engine for PostgreSQL."""
    return create_async_engine(get_database_url())


@asynccontextmanager
async def get_session(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Provide a scoped asynchronous database session."""
    engine = get_engine()
    try:
        async with AsyncSession(engine, expire_on_commit=expire_on_commit) as session:
            yield session
    finally:
        await engine.dispose()
