"""Read and review academic items from the shared database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from src.db.schema import (
    AcademicItem,
    AcademicItemChange,
    Course,
    SourceDocument,
    SourceItemLink,
    SourceRevision,
    Task,
)
from src.db.session import get_session
from src.errors import InvalidInputError, NotFoundError

ALLOWED_ITEM_TYPES = {"assignment", "announcement", "reading", "event"}

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


@dataclass(frozen=True)
class AcademicItemDeletionView:
    id: UUID
    title: str
    course_id: UUID | None
    unlinked_tasks: int
    removed_source_links: int


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
) -> tuple[AcademicItem, AcademicItemChange | None, bool]:
    """Execute review action: confirm, reject, or correct.

    Returns the item, the recorded change (if any), and whether the item
    actually changed. ``reject`` only moves the review state to ``uncertain``;
    it never deletes, merges, hides, or removes the item.
    """
    action = action.lower()
    if action not in {"confirm", "reject", "correct"}:
        raise InvalidInputError(f"Action must be 'confirm', 'reject', or 'correct', got {action!r}")

    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            item = await session.get(AcademicItem, item_id, with_for_update=True)
            if item is None:
                raise NotFoundError(f"Academic item {item_id} was not found.")

            change: AcademicItemChange | None = None
            changed = False
            now = datetime.now(timezone.utc)

            if action == "confirm":
                if item.review_state != "verified":
                    item.review_state = "verified"
                    item.updated_at = now
                    changed = True

            elif action == "reject":
                # A review-state change only. The item itself is never deleted,
                # merged, hidden, or removed by this action.
                if item.review_state != "uncertain":
                    item.review_state = "uncertain"
                    item.updated_at = now
                    changed = True

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
                    if old_val == new_val:
                        continue
                    before_values[key] = str(old_val) if isinstance(old_val, (UUID, Decimal, datetime)) else old_val
                    setattr(item, key, new_val)
                    after_values[key] = str(new_val) if isinstance(new_val, (UUID, Decimal, datetime)) else new_val

                if after_values and note:
                    after_values["_correction_note"] = note

                if item.review_state != "verified":
                    before_values["review_state"] = item.review_state
                    after_values["review_state"] = "verified"
                    item.review_state = "verified"

                if after_values:
                    item.updated_at = now
                    changed = True
                    change = AcademicItemChange(
                        id=uuid4(),
                        academic_item_id=item.id,
                        source_revision_id=item.source_revision_id,
                        origin="student_correction",
                        change_kind="edited",
                        before_values=before_values or None,
                        after_values=after_values,
                        recorded_at=now,
                    )
                    session.add(change)

            await session.flush()
        return item, change, changed


def _change_value(value: Any) -> Any:
    """Render a stored field value as JSON-safe change metadata."""
    return str(value) if isinstance(value, (UUID, Decimal, datetime)) else value


def _item_snapshot(item: AcademicItem) -> dict[str, Any]:
    return {
        "item_type": item.item_type,
        "title": item.title,
        "details": item.details,
        "course_id": _change_value(item.course_id),
        "starts_at": _change_value(item.starts_at),
        "due_at": _change_value(item.due_at),
        "grade_weight_percent": _change_value(item.grade_weight_percent),
        "late_penalty": item.late_penalty,
        "review_state": item.review_state,
    }


async def create_academic_item(
    item_type: str,
    title: str,
    details: str | None = None,
    course_id: UUID | None = None,
    starts_at: datetime | None = None,
    due_at: datetime | None = None,
    grade_weight_percent: Decimal | None = None,
    late_penalty: str | None = None,
) -> AcademicItem:
    """Create a student-authored academic item with no source revision.

    Manual records are marked ``verified`` because the student is the source of
    truth, and a ``created`` change event is recorded so the Inbox feed stays
    honest about where the record came from.
    """
    if item_type not in ALLOWED_ITEM_TYPES:
        raise InvalidInputError(f"item_type must be one of {', '.join(sorted(ALLOWED_ITEM_TYPES))}")

    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            if course_id is not None:
                course = await session.get(Course, course_id)
                if course is None:
                    raise NotFoundError(f"Course {course_id} does not exist.")

            now = datetime.now(timezone.utc)
            item = AcademicItem(
                id=uuid4(),
                course_id=course_id,
                source_revision_id=None,
                item_type=item_type,
                title=title,
                details=details,
                starts_at=starts_at,
                due_at=due_at,
                grade_weight_percent=grade_weight_percent,
                late_penalty=late_penalty,
                review_state="verified",
                created_at=now,
                updated_at=now,
            )
            session.add(item)
            await session.flush()

            session.add(
                AcademicItemChange(
                    id=uuid4(),
                    academic_item_id=item.id,
                    source_revision_id=None,
                    origin="manual",
                    change_kind="created",
                    before_values=None,
                    after_values=_item_snapshot(item),
                    recorded_at=now,
                )
            )
            await session.flush()
        return item


async def update_academic_item(
    item_id: UUID,
    item_type: str | None = None,
    title: str | None = None,
    details: str | None = None,
    clear_details: bool = False,
    course_id: UUID | None = None,
    clear_course: bool = False,
    starts_at: datetime | None = None,
    clear_starts_at: bool = False,
    due_at: datetime | None = None,
    clear_due_at: bool = False,
    grade_weight_percent: Decimal | None = None,
    clear_grade_weight: bool = False,
    late_penalty: str | None = None,
    clear_late_penalty: bool = False,
    review_state: str | None = None,
) -> tuple[AcademicItem, AcademicItemChange | None]:
    """Partially update an academic item and record the edit as a change event.

    Nullable fields are cleared with their ``clear_*`` flags; the non-null
    ``title`` and ``item_type`` are only replaced when provided. An edit marks
    the item ``verified`` unless the caller sets a review state explicitly.
    """
    if item_type is not None and item_type not in ALLOWED_ITEM_TYPES:
        raise InvalidInputError(f"item_type must be one of {', '.join(sorted(ALLOWED_ITEM_TYPES))}")

    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            item = await session.get(AcademicItem, item_id, with_for_update=True)
            if item is None:
                raise NotFoundError(f"Academic item {item_id} was not found.")

            if course_id is not None:
                course = await session.get(Course, course_id)
                if course is None:
                    raise NotFoundError(f"Course {course_id} does not exist.")

            before_values: dict[str, Any] = {}
            after_values: dict[str, Any] = {}

            def apply(field: str, new_value: Any) -> None:
                old_value = getattr(item, field)
                if old_value == new_value:
                    return
                before_values[field] = _change_value(old_value)
                setattr(item, field, new_value)
                after_values[field] = _change_value(new_value)

            if item_type is not None:
                apply("item_type", item_type)
            if title is not None:
                apply("title", title)
            if clear_details:
                apply("details", None)
            elif details is not None:
                apply("details", details)
            if clear_course:
                apply("course_id", None)
            elif course_id is not None:
                apply("course_id", course_id)
            if clear_starts_at:
                apply("starts_at", None)
            elif starts_at is not None:
                apply("starts_at", starts_at)
            if clear_due_at:
                apply("due_at", None)
            elif due_at is not None:
                apply("due_at", due_at)
            if clear_grade_weight:
                apply("grade_weight_percent", None)
            elif grade_weight_percent is not None:
                apply("grade_weight_percent", grade_weight_percent)
            if clear_late_penalty:
                apply("late_penalty", None)
            elif late_penalty is not None:
                apply("late_penalty", late_penalty)

            target_state = review_state or "verified"
            if item.review_state != target_state:
                before_values["review_state"] = item.review_state
                item.review_state = target_state
                after_values["review_state"] = target_state

            change: AcademicItemChange | None = None
            now = datetime.now(timezone.utc)
            if after_values:
                item.updated_at = now
                change = AcademicItemChange(
                    id=uuid4(),
                    academic_item_id=item.id,
                    source_revision_id=item.source_revision_id,
                    origin="student_correction",
                    change_kind="edited",
                    before_values=before_values or None,
                    after_values=after_values,
                    recorded_at=now,
                )
                session.add(change)

            await session.flush()
        return item, change


async def delete_academic_item(item_id: UUID) -> AcademicItemDeletionView:
    """Delete an academic item and the source links and change events it owns.

    Linked tasks are kept and unlinked. The item's source evidence links and
    change history are removed with it, since both reference the item directly.
    """
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            item = await session.get(AcademicItem, item_id, with_for_update=True)
            if item is None:
                raise NotFoundError(f"Academic item {item_id} was not found.")

            task_count = await session.scalar(
                select(func.count()).select_from(Task)
                .where(Task.academic_item_id == item_id)
            )
            link_count = await session.scalar(
                select(func.count()).select_from(SourceItemLink)
                .where(SourceItemLink.academic_item_id == item_id)
            )

            await session.execute(
                update(Task)
                .where(Task.academic_item_id == item_id)
                .values(academic_item_id=None)
            )
            await session.execute(
                delete(SourceItemLink).where(SourceItemLink.academic_item_id == item_id)
            )
            await session.execute(
                delete(AcademicItemChange).where(AcademicItemChange.academic_item_id == item_id)
            )

            deletion = AcademicItemDeletionView(
                id=item.id,
                title=item.title,
                course_id=item.course_id,
                unlinked_tasks=int(task_count or 0),
                removed_source_links=int(link_count or 0),
            )
            await session.delete(item)
            await session.flush()
        return deletion
