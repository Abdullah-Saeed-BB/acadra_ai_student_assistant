"""Persist the console poller's Gmail history cursor in PostgreSQL."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.schema import GmailPollCursor, SourceConnection
from src.services.gmail_connection import _engine


async def read_history_id(connection_id: UUID) -> str | None:
    engine = _engine()
    try:
        async with AsyncSession(engine) as session:
            state = await session.get(GmailPollCursor, connection_id)
            return state.history_id if state else None
    finally:
        await engine.dispose()


async def save_history_id(connection_id: UUID, history_id: str) -> None:
    if not history_id or not history_id.isdecimal():
        raise ValueError("Gmail history ID is invalid.")
    engine = _engine()
    try:
        async with AsyncSession(engine) as session:
            async with session.begin():
                connection = await session.get(SourceConnection, connection_id)
                if connection is None or connection.source_type != "gmail":
                    raise ValueError("Gmail connection was not found.")
                now = datetime.now(timezone.utc)
                state = await session.get(GmailPollCursor, connection_id)
                if state is None:
                    session.add(GmailPollCursor(
                        connection_id=connection_id, history_id=history_id, updated_at=now,
                    ))
                else:
                    state.history_id = history_id
                    state.updated_at = now
                connection.last_synced_at = now
    finally:
        await engine.dispose()
