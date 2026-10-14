"""Read and review academic items from the shared database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from src.db.schema import AcademicItem, AcademicItemChange, Course, SourceDocument, SourceItemLink, SourceRevision
from src.db.session import get_session
from src.errors import InvalidInputError, NotFoundError

ALLOWED_CORRECTION_FIELDS = {
    "title",
    "details",
    "starts_at",
    "due_at",
    "grade_weight_percent",
    "late_penalty",
    "course_id",
}


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


@dataclass(frozen=True)
class AcademicItemDetail:
    item: AcademicItem
    course: Course | None


async def get_academic_item_evidence(item_id: UUID) -> AcademicItemEvidence | None:
    async with get_session() as session:
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
            source_document_id=document.id,
            source_revision_id=link.source_revision_id,
            source_title=document.title,
            source_type=document.source_type,
            evidence=link.evidence,
            review_reasons=link.review_reasons,
            date_facts=link.date_facts,
            original_ref=document.original_ref,
            source_updated_at=revision.source_updated_at,
            observed_at=revision.observed_at,
        )


async def list_academic_items(filters: AcademicItemFilters) -> AcademicItemPage:
    async with get_session() as session:
        return await _list_in_session(session, filters)


async def _list_in_session(
    session, filters: AcademicItemFilters
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


async def get_academic_item(item_id: UUID) -> AcademicItemDetail | None:
    """Retrieve an academic item and its associated course if known."""
    async with get_session() as session:
        item = await session.get(AcademicItem, item_id)
        if item is None:
            return None
        course = None
        if item.course_id is not None:
            course = await session.get(Course, item.course_id)
        return AcademicItemDetail(item=item, course=course)


async def review_academic_item(
    item_id: UUID,
    action: str,
    fields: dict[str, Any] | None = None,
    note: str | None = None,
) -> tuple[AcademicItem, AcademicItemChange | None]:
    """Execute review action: confirm, reject, or correct."""
    action = action.lower()
    if action not in {"confirm", "reject", "correct"}:
        raise InvalidInputError(f"Action must be 'confirm', 'reject', or 'correct', got {action!r}")

    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            item = await session.get(AcademicItem, item_id, with_for_update=True)
            if item is None:
                raise NotFoundError(f"Academic item {item_id} was not found.")

            change: AcademicItemChange | None = None
            now = datetime.now(timezone.utc)

            if action == "confirm":
                item.review_state = "verified"
                item.updated_at = now

            elif action == "reject":
                item.review_state = "uncertain"
                item.updated_at = now

            elif action == "correct":
                if not fields:
                    raise InvalidInputError("fields is required when action is 'correct'")

                disallowed = set(fields.keys()) - ALLOWED_CORRECTION_FIELDS
                if disallowed:
                    raise InvalidInputError(f"Cannot correct fields: {', '.join(sorted(disallowed))}")

                # If course_id is provided, verify it exists
                if "course_id" in fields and fields["course_id"] is not None:
                    course = await session.get(Course, fields["course_id"])
                    if course is None:
                        raise NotFoundError(f"Course {fields['course_id']} does not exist.")

                before_values: dict[str, Any] = {}
                after_values: dict[str, Any] = {}

                for key, new_val in fields.items():
                    old_val = getattr(item, key)
                    before_values[key] = str(old_val) if isinstance(old_val, (UUID, Decimal, datetime)) else old_val
                    setattr(item, key, new_val)
                    after_values[key] = str(new_val) if isinstance(new_val, (UUID, Decimal, datetime)) else new_val

                if note:
                    after_values["_correction_note"] = note

                item.review_state = "verified"
                item.updated_at = now

                change = AcademicItemChange(
                    id=uuid4(),
                    academic_item_id=item.id,
                    source_revision_id=item.source_revision_id,
                    origin="student_correction",
                    change_kind="edited",
                    before_values=before_values,
                    after_values=after_values,
                    recorded_at=now,
                )
                session.add(change)

            await session.flush()
        return item, change
