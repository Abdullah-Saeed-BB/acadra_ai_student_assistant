"""Persist manual text sources and their immutable content revisions."""

from dataclasses import dataclass
from hashlib import sha256
import os
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.connectors.manual import ManualTextEnvelope
from src.db.schema import SourceDocument, SourceRevision


@dataclass(frozen=True)
class ManualTextSaveResult:
    source_document_id: UUID
    source_revision_id: UUID
    revision_no: int
    created_revision: bool


async def save_manual_text(envelope: ManualTextEnvelope) -> ManualTextSaveResult:
    """Save a new source or replace one, serializing updates per document."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to save manual text.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")

    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            async with session.begin():
                return await _save_in_transaction(session, envelope)
    finally:
        await engine.dispose()


async def _save_in_transaction(
    session: AsyncSession, envelope: ManualTextEnvelope
) -> ManualTextSaveResult:
    if envelope.source_document_id is None:
        document = SourceDocument(
            id=uuid4(),
            connection_id=None,
            source_type="text",
            external_id=None,
            original_ref=None,
            title=envelope.title or "Pasted text",
            course_hint=None,
            source_updated_at=None,
            last_seen_at=envelope.observed_at,
        )
        session.add(document)
        await session.flush()
    else:
        document = await session.scalar(
            select(SourceDocument)
            .where(SourceDocument.id == envelope.source_document_id)
            .with_for_update()
        )
        if document is None or document.source_type != "text" or document.connection_id is not None:
            raise ValueError("Manual text source was not found.")
        document.last_seen_at = envelope.observed_at
        if envelope.title is not None:
            document.title = envelope.title

    latest = await session.scalar(
        select(SourceRevision)
        .where(SourceRevision.source_document_id == document.id)
        .order_by(SourceRevision.revision_no.desc())
        .limit(1)
    )
    content_hash = sha256(envelope.clean_text.encode("utf-8")).hexdigest()
    if latest is not None and latest.content_hash == content_hash:
        return ManualTextSaveResult(document.id, latest.id, latest.revision_no, False)

    revision = SourceRevision(
        id=uuid4(),
        source_document_id=document.id,
        revision_no=1 if latest is None else latest.revision_no + 1,
        content_hash=content_hash,
        raw_content=envelope.raw_content,
        clean_text=envelope.clean_text,
        source_updated_at=None,
        observed_at=envelope.observed_at,
    )
    session.add(revision)
    await session.flush()
    return ManualTextSaveResult(document.id, revision.id, revision.revision_no, True)
