"""Persist manual text/file sources and their immutable content revisions."""

import asyncio
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.connectors.manual import ManualTextEnvelope
from src.db.schema import SourceDocument, SourceFile, SourceRevision

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "data" / "uploads"


@dataclass(frozen=True)
class ManualTextSaveResult:
    source_document_id: UUID
    source_revision_id: UUID
    revision_no: int
    created_revision: bool
    file_storage_ref: str | None = None


async def save_manual_text(envelope: ManualTextEnvelope) -> ManualTextSaveResult:
    """Backwards-compatible entry point for pasted text."""
    return await save_manual_source(envelope)


async def save_manual_source(envelope: ManualTextEnvelope) -> ManualTextSaveResult:
    """Save a manual source, serializing updates per document."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to save manual text.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")

    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = None
            try:
                async with session.begin():
                    result = await _save_in_transaction(session, envelope)
                return result
            except Exception:
                if result and result.file_storage_ref:
                    await asyncio.to_thread((Path(__file__).resolve().parents[2] / result.file_storage_ref).unlink, missing_ok=True)
                raise
    finally:
        await engine.dispose()


async def _save_in_transaction(
    session: AsyncSession, envelope: ManualTextEnvelope
) -> ManualTextSaveResult:
    if envelope.source_document_id is None:
        document = SourceDocument(
            id=uuid4(),
            connection_id=None,
            source_type=envelope.source_type,
            external_id=None,
            original_ref=envelope.original_ref,
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
        if document is None or document.source_type != envelope.source_type or document.connection_id is not None:
            raise ValueError("Manual source was not found or its file type differs.")
        document.last_seen_at = envelope.observed_at
        if envelope.title is not None:
            document.title = envelope.title
        if envelope.original_ref is not None:
            document.original_ref = envelope.original_ref

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
    storage_ref = None
    if envelope.file_bytes is not None:
        suffix = ".html" if envelope.source_type == "html" else ".pdf"
        filename = f"{revision.id}{suffix}"
        path = UPLOAD_ROOT / filename
        try:
            await asyncio.to_thread(_write_uploaded_file, path, envelope.file_bytes)
            storage_ref = str(Path("data") / "uploads" / filename)
            session.add(SourceFile(
                id=uuid4(), source_revision_id=revision.id,
                filename=envelope.original_ref or filename,
                media_type=envelope.media_type or "application/octet-stream",
                byte_size=len(envelope.file_bytes),
                content_sha256=sha256(envelope.file_bytes).hexdigest(),
                storage_ref=storage_ref, created_at=envelope.observed_at,
            ))
            await session.flush()
        except Exception:
            await asyncio.to_thread(path.unlink, missing_ok=True)
            raise
    return ManualTextSaveResult(document.id, revision.id, revision.revision_no, True, storage_ref)


def _write_uploaded_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(data)
