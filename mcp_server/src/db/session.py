"""Database engine and session management."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.errors import DatabaseUnavailableError


def get_database_url() -> str:
    """Retrieve and validate the PostgreSQL connection string."""
    url_str = os.getenv("DATABASE_URL")
    if not url_str:
        raise DatabaseUnavailableError(
            message="DATABASE_URL is required but not configured.",
            hint="Set DATABASE_URL in your environment or .env file.",
        )
    url = make_url(url_str)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise DatabaseUnavailableError(
            message="DATABASE_URL must be a PostgreSQL connection URL.",
            hint="Use postgresql+asyncpg://user:pass@host:port/dbname.",
        )
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


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
