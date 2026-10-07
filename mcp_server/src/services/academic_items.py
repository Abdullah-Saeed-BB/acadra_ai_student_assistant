"""Read bounded, filtered academic items from the shared database."""

from dataclasses import dataclass
from datetime import datetime
import os
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.db.schema import AcademicItem, SourceDocument, SourceItemLink, SourceRevision


@dataclass(frozen=True)
class AcademicItemFilters:
    item_type: str | None = None
    course_id: UUID | None = None
    review_state: str | None = None
    due_from: datetime | None = None
    due_before: datetime | None = None
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class AcademicItemPage:
    items: list[AcademicItem]
    has_more: bool


@dataclass(frozen=True)
class AcademicItemEvidence:
    source_document_id: UUID
    source_revision_id: UUID
    source_title: str | None
    source_type: str
    evidence: dict
    review_reasons: list[str]
    date_facts: dict
    original_ref: str | None = None
    source_updated_at: datetime | None = None
    observed_at: datetime | None = None


async def get_academic_item_evidence(item_id: UUID) -> AcademicItemEvidence | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to read academic items.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    try:
        async with AsyncSession(engine) as session:
            row = (await session.execute(
                select(SourceItemLink, SourceDocument, SourceRevision).join(
                    SourceDocument, SourceDocument.id == SourceItemLink.source_document_id
                ).join(SourceRevision, SourceRevision.id == SourceItemLink.source_revision_id)
                .where(SourceItemLink.academic_item_id == item_id).limit(1)
            )).first()
            if row is None:
                return None
            link, document, revision = row
            return AcademicItemEvidence(
                source_document_id=document.id, source_revision_id=link.source_revision_id,
                source_title=document.title, source_type=document.source_type,
                evidence=link.evidence, review_reasons=link.review_reasons,
                date_facts=link.date_facts,
                original_ref=document.original_ref, source_updated_at=revision.source_updated_at,
                observed_at=revision.observed_at,
            )
    finally:
        await engine.dispose()


async def list_academic_items(filters: AcademicItemFilters) -> AcademicItemPage:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to read academic items.")
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")

    engine = create_async_engine(url.set(drivername="postgresql+asyncpg"))
    try:
        async with AsyncSession(engine) as session:
            return await _list_in_session(session, filters)
    finally:
        await engine.dispose()


async def _list_in_session(
    session: AsyncSession, filters: AcademicItemFilters
) -> AcademicItemPage:
    query = select(AcademicItem)
    if filters.item_type is not None:
        query = query.where(AcademicItem.item_type == filters.item_type)
    if filters.course_id is not None:
        query = query.where(AcademicItem.course_id == filters.course_id)
    if filters.review_state is not None:
        query = query.where(AcademicItem.review_state == filters.review_state)
    if filters.due_from is not None:
        query = query.where(AcademicItem.due_at >= filters.due_from)
    if filters.due_before is not None:
        query = query.where(AcademicItem.due_at < filters.due_before)

    query = query.order_by(
        AcademicItem.due_at.asc().nulls_last(),
        AcademicItem.created_at.desc(),
        AcademicItem.id.desc(),
    ).offset(filters.offset).limit(filters.limit + 1)
    rows = list((await session.scalars(query)).all())
    return AcademicItemPage(items=rows[: filters.limit], has_more=len(rows) > filters.limit)
