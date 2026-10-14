"""Change feed service reading academic_item_changes with item context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.db.schema import AcademicItem, AcademicItemChange
from src.db.session import get_session


@dataclass(frozen=True)
class ChangeItemView:
    id: UUID
    academic_item_id: UUID
    source_revision_id: UUID | None
    origin: str
    change_kind: str
    before_values: dict[str, Any] | None
    after_values: dict[str, Any]
    recorded_at: datetime
    title: str | None
    item_type: str | None


@dataclass(frozen=True)
class ChangesPage:
    items: list[ChangeItemView]
    has_more: bool


async def get_changes_since(
    since: datetime | None = None,
    item_type: str | None = None,
    course_id: UUID | None = None,
    change_kind: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ChangesPage:
    """Read change events with joined academic item title and item_type."""
    async with get_session() as session:
        query = (
            select(AcademicItemChange, AcademicItem.title, AcademicItem.item_type)
            .join(AcademicItem, AcademicItem.id == AcademicItemChange.academic_item_id)
        )

        if since is not None:
            query = query.where(AcademicItemChange.recorded_at > since)
        if item_type is not None:
            query = query.where(AcademicItem.item_type == item_type)
        if course_id is not None:
            query = query.where(AcademicItem.course_id == course_id)
        if change_kind is not None:
            query = query.where(AcademicItemChange.change_kind == change_kind)

        query = (
            query.order_by(AcademicItemChange.recorded_at.desc(), AcademicItemChange.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )

        rows = (await session.execute(query)).all()
        has_more = len(rows) > limit
        selected_rows = rows[:limit]

        views = [
            ChangeItemView(
                id=change.id,
                academic_item_id=change.academic_item_id,
                source_revision_id=change.source_revision_id,
                origin=change.origin,
                change_kind=change.change_kind,
                before_values=change.before_values,
                after_values=change.after_values,
                recorded_at=change.recorded_at,
                title=title,
                item_type=item_type_val,
            )
            for change, title, item_type_val in selected_rows
        ]
        return ChangesPage(items=views, has_more=has_more)
