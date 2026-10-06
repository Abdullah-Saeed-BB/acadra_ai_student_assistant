"""Single-user Gmail account configuration and credential reference storage."""

import os
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.auth.credential_store import delete_gmail_refresh_token, save_gmail_refresh_token
from src.db.schema import SourceConnection


def _engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for Gmail configuration.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    return create_async_engine(url.set(drivername="postgresql+asyncpg"))


async def get_gmail_connection() -> SourceConnection | None:
    engine = _engine()
    try:
        async with AsyncSession(engine) as session:
            return await session.scalar(
                select(SourceConnection).where(SourceConnection.source_type == "gmail").limit(1)
            )
    finally:
        await engine.dispose()


async def save_gmail_configuration(allowed_senders: list[str]) -> tuple[SourceConnection, bool]:
    """Create or replace the sender allowlist before Gmail can be connected."""
    engine = _engine()
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                connection = await session.scalar(
                    select(SourceConnection).where(SourceConnection.source_type == "gmail")
                    .with_for_update().limit(1)
                )
                created = connection is None
                if connection is None:
                    connection = SourceConnection(
                        id=uuid4(), source_type="gmail", account_label="Gmail account",
                        external_account_id=None, credential_ref=None,
                        allowed_senders=allowed_senders, status="not_connected",
                        last_synced_at=None,
                    )
                    session.add(connection)
                else:
                    connection.allowed_senders = allowed_senders
                await session.flush()
            return connection, created
    finally:
        await engine.dispose()


async def connect_gmail_account(connection_id: UUID, email: str, refresh_token: str) -> None:
    """Bind the consented Gmail account to the configured connection."""
    engine = _engine()
    new_ref = None
    old_ref = None
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                connection = await session.scalar(
                    select(SourceConnection).where(
                        SourceConnection.id == connection_id,
                        SourceConnection.source_type == "gmail",
                    ).with_for_update()
                )
                if connection is None or not connection.allowed_senders:
                    raise ValueError("Save allowed senders before connecting Gmail.")
                if connection.external_account_id and connection.external_account_id != email:
                    raise ValueError("This connection belongs to another Gmail account.")
                old_ref = connection.credential_ref
                new_ref = await save_gmail_refresh_token(refresh_token)
                connection.account_label = email
                connection.external_account_id = email
                connection.credential_ref = new_ref
                connection.status = "connected"
                await session.flush()
        if old_ref:
            try:
                await delete_gmail_refresh_token(old_ref)
            except Exception:
                pass  # Existing secret cleanup can be retried without losing the new connection.
    except Exception:
        if new_ref:
            try:
                await delete_gmail_refresh_token(new_ref)
            except Exception:
                pass
        raise
    finally:
        await engine.dispose()
