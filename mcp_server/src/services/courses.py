"""Courses service querying and managing courses and their associated academic items."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from src.db.schema import AcademicItem, Course, Task
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


@dataclass(frozen=True)
class CourseDeletionView:
    id: UUID
    name: str
    unlinked_items: int
    unlinked_tasks: int


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


async def create_course(
    name: str,
    code: str | None = None,
    term: str | None = None,
) -> Course:
    """Create a course the student can attach academic items and tasks to."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            course = Course(
                id=uuid4(),
                code=code,
                name=name,
                term=term,
                created_at=datetime.now(timezone.utc),
            )
            session.add(course)
            await session.flush()
        return course


async def update_course(
    course_id: UUID,
    name: str | None = None,
    code: str | None = None,
    clear_code: bool = False,
    term: str | None = None,
    clear_term: bool = False,
) -> Course:
    """Partially update a course.

    ``name`` is required by the database, so it is only replaced when provided.
    The nullable ``code`` and ``term`` are cleared with their ``clear_*`` flags.
    """
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            course = await session.get(Course, course_id, with_for_update=True)
            if course is None:
                raise NotFoundError(f"Course {course_id} was not found.")

            if name is not None:
                course.name = name
            if clear_code:
                course.code = None
            elif code is not None:
                course.code = code
            if clear_term:
                course.term = None
            elif term is not None:
                course.term = term

            await session.flush()
        return course


async def delete_course(course_id: UUID) -> CourseDeletionView:
    """Delete a course, keeping the academic items and tasks it referenced.

    Removing a course only clears the course link on its academic items and
    tasks; the records themselves are never deleted here.
    """
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            course = await session.get(Course, course_id, with_for_update=True)
            if course is None:
                raise NotFoundError(f"Course {course_id} was not found.")

            item_count = await session.scalar(
                select(func.count()).select_from(AcademicItem)
                .where(AcademicItem.course_id == course_id)
            )
            task_count = await session.scalar(
                select(func.count()).select_from(Task)
                .where(Task.course_id == course_id)
            )

            await session.execute(
                update(AcademicItem)
                .where(AcademicItem.course_id == course_id)
                .values(course_id=None)
            )
            await session.execute(
                update(Task)
                .where(Task.course_id == course_id)
                .values(course_id=None)
            )

            deletion = CourseDeletionView(
                id=course.id,
                name=course.name,
                unlinked_items=int(item_count or 0),
                unlinked_tasks=int(task_count or 0),
            )
            await session.delete(course)
            await session.flush()
        return deletion
