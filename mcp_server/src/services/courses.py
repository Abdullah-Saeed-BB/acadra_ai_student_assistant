"""Courses service querying registered courses and their associated academic items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from src.db.schema import AcademicItem, Course
from src.db.session import get_session
from src.errors import NotFoundError


@dataclass(frozen=True)
class CourseSummaryView:
    id: UUID
    code: str | None
    name: str
    term: str | None
    item_count: int
    created_at: datetime


@dataclass(frozen=True)
class CoursesPage:
    items: list[CourseSummaryView]
    has_more: bool


@dataclass(frozen=True)
class CourseDetailView:
    id: UUID
    code: str | None
    name: str
    term: str | None
    created_at: datetime
    academic_items: list[dict[str, Any]]


async def list_courses(limit: int = 20, offset: int = 0) -> CoursesPage:
    """List courses with aggregated academic item counts ordered by name."""
    async with get_session() as session:
        query = (
            select(
                Course,
                func.count(AcademicItem.id).label("item_count"),
            )
            .outerjoin(AcademicItem, AcademicItem.course_id == Course.id)
            .group_by(Course.id)
            .order_by(Course.name.asc(), Course.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        rows = (await session.execute(query)).all()
        has_more = len(rows) > limit
        selected_rows = rows[:limit]

        views = [
            CourseSummaryView(
                id=course.id,
                code=course.code,
                name=course.name,
                term=course.term,
                item_count=count,
                created_at=course.created_at,
            )
            for course, count in selected_rows
        ]
        return CoursesPage(items=views, has_more=has_more)


async def get_course(course_id: UUID) -> CourseDetailView:
    """Retrieve course and all associated academic items ordered by due date."""
    async with get_session() as session:
        course = await session.get(Course, course_id)
        if course is None:
            raise NotFoundError(f"Course {course_id} was not found.")

        items_rows = (await session.scalars(
            select(AcademicItem)
            .where(AcademicItem.course_id == course_id)
            .order_by(AcademicItem.due_at.asc().nulls_last(), AcademicItem.created_at.desc())
        )).all()

        items_data = [
            {
                "id": str(item.id),
                "title": item.title,
                "item_type": item.item_type,
                "review_state": item.review_state,
                "due_at": item.due_at.isoformat() if item.due_at else None,
                "grade_weight_percent": float(item.grade_weight_percent) if item.grade_weight_percent is not None else None,
            }
            for item in items_rows
        ]

        return CourseDetailView(
            id=course.id,
            code=course.code,
            name=course.name,
            term=course.term,
            created_at=course.created_at,
            academic_items=items_data,
        )
