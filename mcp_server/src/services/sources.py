"""Source documents and revisions query service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.db.schema import AcademicItem, AcademicItemChange, SourceDocument, SourceItemLink, SourceRevision
from src.db.session import get_session
from src.errors import NotFoundError


@dataclass(frozen=True)
class SourceSummaryView:
    id: UUID
    source_type: str
    title: str | None
    original_ref: str | None
    course_hint: str | None
    latest_revision_no: int | None
    observed_at: datetime | None
    has_review_candidates: bool
    last_change_at: datetime | None


@dataclass(frozen=True)
class SourcesPage:
    items: list[SourceSummaryView]
    has_more: bool


@dataclass(frozen=True)
class RevisionView:
    id: UUID
    revision_no: int
    content_hash: str
    observed_at: datetime
    source_updated_at: datetime | None


@dataclass(frozen=True)
class SourceDetailView:
    id: UUID
    source_type: str
    title: str | None
    original_ref: str | None
    course_hint: str | None
    revisions: list[RevisionView]
    academic_items: list[dict[str, Any]]
    has_review_candidates: bool
    last_change_at: datetime | None


async def list_sources(
    source_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SourcesPage:
    """List saved sources with latest revision and processing state."""
    async with get_session() as session:
        query = select(SourceDocument)
        if source_type is not None:
            query = query.where(SourceDocument.source_type == source_type)

        query = query.order_by(SourceDocument.last_seen_at.desc(), SourceDocument.id.desc()).offset(offset).limit(limit + 1)
        docs = list((await session.scalars(query)).all())
        has_more = len(docs) > limit
        selected_docs = docs[:limit]

        views: list[SourceSummaryView] = []
        for doc in selected_docs:
            latest_rev = (await session.execute(
                select(SourceRevision.revision_no, SourceRevision.observed_at)
                .where(SourceRevision.source_document_id == doc.id)
                .order_by(SourceRevision.revision_no.desc())
                .limit(1)
            )).first()

            rev_no = latest_rev[0] if latest_rev else None
            obs_at = latest_rev[1] if latest_rev else doc.last_seen_at

            # A link is a review candidate when extraction recorded review reasons.
            candidate_count = await session.scalar(
                select(func.count(SourceItemLink.id))
                .where(
                    SourceItemLink.source_document_id == doc.id,
                    func.json_array_length(SourceItemLink.review_reasons) > 0,
                )
            ) or 0

            # Check last change
            last_change = await session.scalar(
                select(func.max(AcademicItemChange.recorded_at))
                .join(SourceRevision, SourceRevision.id == AcademicItemChange.source_revision_id)
                .where(SourceRevision.source_document_id == doc.id)
            )

            views.append(
                SourceSummaryView(
                    id=doc.id,
                    source_type=doc.source_type,
                    title=doc.title,
                    original_ref=doc.original_ref,
                    course_hint=doc.course_hint,
                    latest_revision_no=rev_no,
                    observed_at=obs_at,
                    has_review_candidates=bool(candidate_count > 0),
                    last_change_at=last_change,
                )
            )

        return SourcesPage(items=views, has_more=has_more)


async def get_source_detail(source_document_id: UUID) -> SourceDetailView:
    """Get full source document details including all revisions and produced items."""
    async with get_session() as session:
        doc = await session.get(SourceDocument, source_document_id)
        if doc is None:
            raise NotFoundError(f"Source document {source_document_id} was not found.")

        revisions_rows = (await session.scalars(
            select(SourceRevision)
            .where(SourceRevision.source_document_id == source_document_id)
            .order_by(SourceRevision.revision_no.asc())
        )).all()

        rev_views = [
            RevisionView(
                id=rev.id,
                revision_no=rev.revision_no,
                content_hash=rev.content_hash,
                observed_at=rev.observed_at,
                source_updated_at=rev.source_updated_at,
            )
            for rev in revisions_rows
        ]

        # Academic items linked to this document's revisions
        rev_ids = [rev.id for rev in revisions_rows]
        items_rows = (await session.scalars(
            select(AcademicItem)
            .where(AcademicItem.source_revision_id.in_(rev_ids))
            .order_by(AcademicItem.created_at.desc())
        )).all() if rev_ids else []

        items_summary = [
            {
                "id": str(item.id),
                "title": item.title,
                "item_type": item.item_type,
                "review_state": item.review_state,
                "due_at": item.due_at.isoformat() if item.due_at else None,
            }
            for item in items_rows
        ]

        candidate_count = await session.scalar(
            select(func.count(SourceItemLink.id))
            .where(
                SourceItemLink.source_document_id == source_document_id,
                func.json_array_length(SourceItemLink.review_reasons) > 0,
            )
        ) or 0

        last_change = await session.scalar(
            select(func.max(AcademicItemChange.recorded_at))
            .where(AcademicItemChange.source_revision_id.in_(rev_ids))
        ) if rev_ids else None

        return SourceDetailView(
            id=doc.id,
            source_type=doc.source_type,
            title=doc.title,
            original_ref=doc.original_ref,
            course_hint=doc.course_hint,
            revisions=rev_views,
            academic_items=items_summary,
            has_review_candidates=bool(candidate_count > 0),
            last_change_at=last_change,
        )
