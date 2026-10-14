"""Tasks and planning service handling task lifecycle, kanban views, and plan scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB

from src.db.schema import AcademicItem, Course, Task
from src.db.session import get_session
from src.errors import InvalidInputError, NotFoundError


@dataclass(frozen=True)
class TaskDetailView:
    task: Task
    steps: list[Task]
    progress: dict[str, int]
    academic_item: dict[str, Any] | None
    course: dict[str, Any] | None


@dataclass(frozen=True)
class TasksPage:
    items: list[Task]
    has_more: bool


@dataclass(frozen=True)
class TodayPlanView:
    day: date
    tasks: list[Task]
    total_estimated_minutes: int


@dataclass(frozen=True)
class DayPlanGroup:
    day: date
    total_estimated_minutes: int
    tasks: list[Task]


@dataclass(frozen=True)
class UpcomingPlanView:
    days: list[DayPlanGroup]
    start_day: date
    end_day: date


@dataclass(frozen=True)
class BacklogView:
    tasks: list[Task]
    total_estimated_minutes: int
    limit: int
    offset: int
    has_more: bool


@dataclass(frozen=True)
class PlanBoardView:
    columns: list[dict[str, Any]]
    backlog: list[Task]


async def list_tasks(
    status: str | None = None,
    selected_day: date | None = None,
    selected_from: date | None = None,
    selected_to: date | None = None,
    has_selected_day: bool | None = None,
    parent_task_id: UUID | None = None,
    academic_item_id: UUID | None = None,
    course_id: UUID | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> TasksPage:
    """Read planned tasks with bounded filtering and canonical ordering."""
    async with get_session() as session:
        query = select(Task)

        if status is not None:
            query = query.where(Task.status == status)
        if selected_day is not None:
            query = query.where(Task.selected_day == selected_day)
        if selected_from is not None:
            query = query.where(Task.selected_day >= selected_from)
        if selected_to is not None:
            query = query.where(Task.selected_day <= selected_to)
        if has_selected_day is not None:
            if has_selected_day:
                query = query.where(Task.selected_day.is_not(None))
            else:
                query = query.where(Task.selected_day.is_(None))
        if parent_task_id is not None:
            query = query.where(Task.parent_task_id == parent_task_id)
        if academic_item_id is not None:
            query = query.where(Task.academic_item_id == academic_item_id)
        if course_id is not None:
            query = query.where(Task.course_id == course_id)
        if tag is not None:
            query = query.where(cast(Task.tags, JSONB).contains([tag]))

        # Ordering: selected_day ASC (undated after dated), then list_position ASC, then created_at DESC
        query = (
            query.order_by(
                Task.selected_day.asc().nulls_last(),
                Task.list_position.asc(),
                Task.created_at.desc(),
                Task.id.desc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )

        rows = list((await session.scalars(query)).all())
        has_more = len(rows) > limit
        return TasksPage(items=rows[:limit], has_more=has_more)


async def get_task(task_id: UUID) -> TaskDetailView:
    """Retrieve a task with its child steps, derived progress, and related links."""
    async with get_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} was not found.")

        steps_rows = list((await session.scalars(
            select(Task)
            .where(Task.parent_task_id == task_id)
            .order_by(Task.list_position.asc(), Task.created_at.asc())
        )).all())

        total_steps = len(steps_rows)
        completed_steps = sum(1 for step in steps_rows if step.status == "done")
        unfinished_steps = total_steps - completed_steps

        progress = {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "unfinished_steps": unfinished_steps,
        }

        academic_item_dict = None
        if task.academic_item_id:
            item = await session.get(AcademicItem, task.academic_item_id)
            if item:
                academic_item_dict = {
                    "id": str(item.id),
                    "title": item.title,
                    "item_type": item.item_type,
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                }

        course_dict = None
        if task.course_id:
            course = await session.get(Course, task.course_id)
            if course:
                course_dict = {
                    "id": str(course.id),
                    "code": course.code,
                    "name": course.name,
                }

        return TaskDetailView(
            task=task,
            steps=steps_rows,
            progress=progress,
            academic_item=academic_item_dict,
            course=course_dict,
        )


async def create_task(
    title: str,
    details: str | None = None,
    selected_day: date | None = None,
    estimated_minutes: int | None = None,
    tags: list[str] | None = None,
    academic_item_id: UUID | None = None,
    course_id: UUID | None = None,
    parent_task_id: UUID | None = None,
) -> Task:
    """Create a task or step, computing the next list position."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            if parent_task_id:
                parent = await session.get(Task, parent_task_id)
                if parent is None:
                    raise NotFoundError(f"Parent task {parent_task_id} does not exist.")
                if academic_item_id is None:
                    academic_item_id = parent.academic_item_id
                if course_id is None:
                    course_id = parent.course_id

            if academic_item_id:
                item = await session.get(AcademicItem, academic_item_id)
                if item is None:
                    raise NotFoundError(f"Academic item {academic_item_id} does not exist.")

            if course_id:
                course = await session.get(Course, course_id)
                if course is None:
                    raise NotFoundError(f"Course {course_id} does not exist.")

            # Compute next list_position on that day
            if selected_day is not None:
                max_pos = await session.scalar(
                    select(func.coalesce(func.max(Task.list_position), -1))
                    .where(Task.selected_day == selected_day)
                )
            else:
                max_pos = await session.scalar(
                    select(func.coalesce(func.max(Task.list_position), -1))
                    .where(Task.selected_day.is_(None))
                )

            next_pos = (max_pos if max_pos is not None else -1) + 1
            now = datetime.now(timezone.utc)

            task = Task(
                id=uuid4(),
                title=title,
                details=details,
                status="todo",
                selected_day=selected_day,
                list_position=next_pos,
                estimated_minutes=estimated_minutes,
                tags=tags or [],
                academic_item_id=academic_item_id,
                course_id=course_id,
                parent_task_id=parent_task_id,
                completed_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(task)
            await session.flush()
        return task


async def update_task(
    task_id: UUID,
    title: str | None = None,
    details: str | None = None,
    status: str | None = None,
    selected_day: date | None = None,
    clear_selected_day: bool = False,
    list_position: int | None = None,
    estimated_minutes: int | None = None,
    tags: list[str] | None = None,
    parent_task_id: UUID | None = None,
) -> Task:
    """Partially update an existing task."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            task = await session.get(Task, task_id, with_for_update=True)
            if task is None:
                raise NotFoundError(f"Task {task_id} was not found.")

            now = datetime.now(timezone.utc)

            if title is not None:
                task.title = title
            if details is not None:
                task.details = details
            if status is not None:
                if status == "done" and task.status != "done":
                    task.completed_at = now
                elif status != "done" and task.status == "done":
                    task.completed_at = None
                task.status = status
            if clear_selected_day:
                task.selected_day = None
            elif selected_day is not None:
                task.selected_day = selected_day
            if list_position is not None:
                task.list_position = list_position
            if estimated_minutes is not None:
                task.estimated_minutes = estimated_minutes
            if tags is not None:
                task.tags = tags
            if parent_task_id is not None:
                parent = await session.get(Task, parent_task_id)
                if parent is None:
                    raise NotFoundError(f"Parent task {parent_task_id} does not exist.")
                task.parent_task_id = parent_task_id

            task.updated_at = now
            await session.flush()
        return task


async def move_task(task_id: UUID, selected_day: date | None) -> Task:
    """Move a task to a selected day or backlog."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            task = await session.get(Task, task_id, with_for_update=True)
            if task is None:
                raise NotFoundError(f"Task {task_id} was not found.")

            if task.selected_day == selected_day:
                return task

            if selected_day is not None:
                max_pos = await session.scalar(
                    select(func.coalesce(func.max(Task.list_position), -1))
                    .where(Task.selected_day == selected_day)
                )
            else:
                max_pos = await session.scalar(
                    select(func.coalesce(func.max(Task.list_position), -1))
                    .where(Task.selected_day.is_(None))
                )

            next_pos = (max_pos if max_pos is not None else -1) + 1
            task.selected_day = selected_day
            task.list_position = next_pos
            task.updated_at = datetime.now(timezone.utc)
            await session.flush()
        return task


async def reorder_tasks(selected_day: date | None, task_ids: list[UUID]) -> list[Task]:
    """Reorder tasks for a given day according to task_ids sequence."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            updated_tasks: list[Task] = []
            for position, tid in enumerate(task_ids):
                task = await session.get(Task, tid, with_for_update=True)
                if task is None:
                    raise NotFoundError(f"Task {tid} in reorder list was not found.")
                task.selected_day = selected_day
                task.list_position = position
                task.updated_at = now
                updated_tasks.append(task)
            await session.flush()
        return updated_tasks


async def complete_task(task_id: UUID, done: bool) -> Task:
    """Mark a task done or todo."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            task = await session.get(Task, task_id, with_for_update=True)
            if task is None:
                raise NotFoundError(f"Task {task_id} was not found.")

            now = datetime.now(timezone.utc)
            if done:
                task.status = "done"
                task.completed_at = now
            else:
                task.status = "todo"
                task.completed_at = None
            task.updated_at = now
            await session.flush()
        return task


async def split_task(
    task_id: UUID,
    steps: list[dict[str, Any]],
    replace_existing: bool = False,
) -> tuple[Task, list[Task]]:
    """Split a parent task into child step tasks."""
    async with get_session(expire_on_commit=False) as session:
        async with session.begin():
            parent = await session.get(Task, task_id, with_for_update=True)
            if parent is None:
                raise NotFoundError(f"Task {task_id} was not found.")

            if replace_existing:
                await session.execute(
                    delete(Task).where(Task.parent_task_id == task_id)
                )

            now = datetime.now(timezone.utc)
            created_steps: list[Task] = []

            for idx, step_data in enumerate(steps):
                step_title = step_data["title"]
                step_day = step_data.get("selected_day", parent.selected_day)
                step_est = step_data.get("estimated_minutes")

                step = Task(
                    id=uuid4(),
                    title=step_title,
                    details=None,
                    status="todo",
                    selected_day=step_day,
                    list_position=idx,
                    estimated_minutes=step_est,
                    tags=parent.tags or [],
                    academic_item_id=parent.academic_item_id,
                    course_id=parent.course_id,
                    parent_task_id=task_id,
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(step)
                created_steps.append(step)

            parent.updated_at = now
            await session.flush()
        return parent, created_steps


async def get_today_plan(day: date | None = None, timezone_name: str | None = None) -> TodayPlanView:
    """Retrieve ordered tasks selected for today and sum estimated minutes."""
    if day is None:
        if timezone_name:
            try:
                tz = ZoneInfo(timezone_name)
                day = datetime.now(tz).date()
            except Exception:
                day = datetime.now(timezone.utc).date()
        else:
            day = datetime.now(timezone.utc).date()

    async with get_session() as session:
        tasks = list((await session.scalars(
            select(Task)
            .where(Task.selected_day == day)
            .order_by(Task.list_position.asc(), Task.created_at.asc())
        )).all())

        total_minutes = sum(t.estimated_minutes or 0 for t in tasks)
        return TodayPlanView(day=day, tasks=tasks, total_estimated_minutes=total_minutes)


async def get_upcoming_plan(days: int = 7, start_day: date | None = None) -> UpcomingPlanView:
    """Group tasks across upcoming days with workload estimates."""
    if start_day is None:
        start_day = datetime.now(timezone.utc).date()
    end_day = start_day + timedelta(days=days - 1)

    async with get_session() as session:
        tasks = list((await session.scalars(
            select(Task)
            .where(Task.selected_day >= start_day, Task.selected_day <= end_day)
            .order_by(Task.selected_day.asc(), Task.list_position.asc())
        )).all())

        tasks_by_day: dict[date, list[Task]] = {start_day + timedelta(days=i): [] for i in range(days)}
        for t in tasks:
            if t.selected_day in tasks_by_day:
                tasks_by_day[t.selected_day].append(t)

        groups = [
            DayPlanGroup(
                day=d,
                total_estimated_minutes=sum(t.estimated_minutes or 0 for t in day_tasks),
                tasks=day_tasks,
            )
            for d, day_tasks in tasks_by_day.items()
        ]

        return UpcomingPlanView(days=groups, start_day=start_day, end_day=end_day)


async def get_backlog(limit: int = 20, offset: int = 0) -> BacklogView:
    """Retrieve unfinished tasks without a selected day."""
    async with get_session() as session:
        query = (
            select(Task)
            .where(Task.selected_day.is_(None), Task.status != "done")
            .order_by(Task.list_position.asc(), Task.created_at.desc())
        )

        total_minutes = await session.scalar(
            select(func.coalesce(func.sum(Task.estimated_minutes), 0))
            .where(Task.selected_day.is_(None), Task.status != "done")
        ) or 0

        rows = list((await session.scalars(query.offset(offset).limit(limit + 1))).all())
        has_more = len(rows) > limit

        return BacklogView(
            tasks=rows[:limit],
            total_estimated_minutes=int(total_minutes),
            limit=limit,
            offset=offset,
            has_more=has_more,
        )


async def get_plan_board(start_day: date | None = None, days: int = 7) -> PlanBoardView:
    """Kanban plan board with columns for scheduled days plus backlog."""
    upcoming = await get_upcoming_plan(days=days, start_day=start_day)
    backlog_res = await get_backlog(limit=100, offset=0)

    columns = [
        {
            "day": group.day.isoformat(),
            "total_estimated_minutes": group.total_estimated_minutes,
            "tasks": group.tasks,
        }
        for group in upcoming.days
    ]

    return PlanBoardView(columns=columns, backlog=backlog_res.tasks)
