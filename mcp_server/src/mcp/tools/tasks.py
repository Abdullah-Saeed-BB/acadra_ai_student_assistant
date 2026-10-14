"""MCP tools for task management, plan views, and kanban planning."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors, InvalidInputError
from src.mcp.responses import format_read_response, paginate_response
from src.mcp.schemas import StepItem
from src.services.tasks import (
    complete_task,
    create_task,
    get_backlog,
    get_plan_board,
    get_task,
    get_today_plan,
    get_upcoming_plan,
    list_tasks,
    move_task,
    reorder_tasks,
    split_task,
    update_task,
)


def _serialize_task(task: Any) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "details": task.details,
        "status": task.status,
        "selected_day": task.selected_day.isoformat() if task.selected_day else None,
        "list_position": task.list_position,
        "estimated_minutes": task.estimated_minutes,
        "tags": task.tags or [],
        "academic_item_id": str(task.academic_item_id) if task.academic_item_id else None,
        "course_id": str(task.course_id) if task.course_id else None,
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_list_tasks",
        description=(
            "List planned tasks with filters for status, selected day, date ranges, backlog state, "
            "and tags. Ordered by selected day (undated last), then list position."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_list_tasks(
        status: Annotated[Literal["todo", "in_progress", "done"] | None, Field(default=None, description="Task status filter")] = None,
        selected_day: Annotated[date | None, Field(default=None, description="Exact YYYY-MM-DD match")] = None,
        selected_from: Annotated[date | None, Field(default=None, description="Inclusive start date")] = None,
        selected_to: Annotated[date | None, Field(default=None, description="Inclusive end date")] = None,
        has_selected_day: Annotated[bool | None, Field(default=None, description="False returns only Backlog tasks")] = None,
        parent_task_id: Annotated[str | None, Field(default=None, description="Filter children of this parent UUID")] = None,
        academic_item_id: Annotated[str | None, Field(default=None, description="Filter tasks linked to this academic item UUID")] = None,
        course_id: Annotated[str | None, Field(default=None, description="Filter tasks for this course UUID")] = None,
        tag: Annotated[str | None, Field(default=None, max_length=50, description="Tag filter")] = None,
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        p_parent = UUID(parent_task_id) if parent_task_id else None
        p_item = UUID(academic_item_id) if academic_item_id else None
        p_course = UUID(course_id) if course_id else None

        page = await list_tasks(
            status=status,
            selected_day=selected_day,
            selected_from=selected_from,
            selected_to=selected_to,
            has_selected_day=has_selected_day,
            parent_task_id=p_parent,
            academic_item_id=p_item,
            course_id=p_course,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        serialized = [_serialize_task(t) for t in page.items]
        paged = paginate_response(serialized, limit=limit, offset=offset, has_more=page.has_more)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- [{'x' if t['status'] == 'done' else ' '}] **{t['title']}** (Day: {t['selected_day'] or 'Backlog'}, {t['estimated_minutes'] or 0}m)" for t in serialized]
            markdown_summary = f"### Tasks ({len(serialized)})\n" + "\n".join(lines)

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_task",
        description="Retrieve a single task with its child steps, derived progress counts, and linked academic item/course.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_task(
        task_id: Annotated[str, Field(description="Task UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(task_id)
        except ValueError:
            raise InvalidInputError("task_id must be a valid UUID.") from None

        detail = await get_task(parsed_id)
        res = _serialize_task(detail.task)
        res["steps"] = [_serialize_task(s) for s in detail.steps]
        res["progress"] = detail.progress
        res["academic_item"] = detail.academic_item
        res["course"] = detail.course
        return res

    @mcp.tool(
        name="study_create_task",
        description="Create a new task or child step. If selected_day is omitted, the task goes to the Backlog.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_create_task(
        title: Annotated[str, Field(min_length=1, max_length=200, description="Task title")],
        details: Annotated[str | None, Field(default=None, max_length=2000, description="Detailed task notes")] = None,
        selected_day: Annotated[date | None, Field(default=None, description="Target execution date, or omit for backlog")] = None,
        estimated_minutes: Annotated[int | None, Field(default=None, ge=1, le=1440, description="Estimated effort in minutes")] = None,
        tags: Annotated[list[str] | None, Field(default=None, description="Task tags (up to 10 tags, each <= 50 chars)")] = None,
        academic_item_id: Annotated[str | None, Field(default=None, description="Optional academic item UUID to link")] = None,
        course_id: Annotated[str | None, Field(default=None, description="Optional course UUID to link")] = None,
        parent_task_id: Annotated[str | None, Field(default=None, description="Optional parent task UUID if creating a step")] = None,
    ) -> dict[str, Any]:
        p_item = UUID(academic_item_id) if academic_item_id else None
        p_course = UUID(course_id) if course_id else None
        p_parent = UUID(parent_task_id) if parent_task_id else None

        task = await create_task(
            title=title,
            details=details,
            selected_day=selected_day,
            estimated_minutes=estimated_minutes,
            tags=tags,
            academic_item_id=p_item,
            course_id=p_course,
            parent_task_id=p_parent,
        )
        return _serialize_task(task)

    @mcp.tool(
        name="study_update_task",
        description="Partially update a task's fields: title, details, status, selected day, list position, effort, tags, or parent.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_update_task(
        task_id: Annotated[str, Field(description="Task UUID")],
        title: Annotated[str | None, Field(default=None, min_length=1, max_length=200)] = None,
        details: Annotated[str | None, Field(default=None, max_length=2000)] = None,
        status: Annotated[Literal["todo", "in_progress", "done"] | None, Field(default=None)] = None,
        selected_day: Annotated[date | None, Field(default=None)] = None,
        clear_selected_day: Annotated[bool, Field(default=False, description="Set true to move task to backlog")] = False,
        list_position: Annotated[int | None, Field(default=None, ge=0)] = None,
        estimated_minutes: Annotated[int | None, Field(default=None, ge=1, le=1440)] = None,
        tags: Annotated[list[str] | None, Field(default=None)] = None,
        parent_task_id: Annotated[str | None, Field(default=None)] = None,
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(task_id)
        except ValueError:
            raise InvalidInputError("task_id must be a valid UUID.") from None

        p_parent = UUID(parent_task_id) if parent_task_id else None

        updated = await update_task(
            task_id=parsed_id,
            title=title,
            details=details,
            status=status,
            selected_day=selected_day,
            clear_selected_day=clear_selected_day,
            list_position=list_position,
            estimated_minutes=estimated_minutes,
            tags=tags,
            parent_task_id=p_parent,
        )
        return _serialize_task(updated)

    @mcp.tool(
        name="study_move_task",
        description="Change or clear a task's selected work day (moving to None sends it to Backlog).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_move_task(
        task_id: Annotated[str, Field(description="Task UUID")],
        selected_day: Annotated[date | None, Field(default=None, description="Target date, or null to move to Backlog")] = None,
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(task_id)
        except ValueError:
            raise InvalidInputError("task_id must be a valid UUID.") from None

        moved = await move_task(parsed_id, selected_day)
        return _serialize_task(moved)

    @mcp.tool(
        name="study_reorder_tasks",
        description="Rewrite the list positions for tasks on a given selected day (or backlog) based on provided task UUIDs.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_reorder_tasks(
        task_ids: Annotated[list[str], Field(min_length=1, description="Ordered list of task UUIDs")],
        selected_day: Annotated[date | None, Field(default=None, description="The day whose list is being reordered (null for backlog)")] = None,
    ) -> dict[str, Any]:
        parsed_ids = [UUID(tid) for tid in task_ids]
        updated = await reorder_tasks(selected_day=selected_day, task_ids=parsed_ids)
        return {
            "selected_day": selected_day.isoformat() if selected_day else None,
            "tasks": [_serialize_task(t) for t in updated],
        }

    @mcp.tool(
        name="study_complete_task",
        description="Mark a task as completed (done=true) or return it to todo (done=false). Idempotent.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_complete_task(
        task_id: Annotated[str, Field(description="Task UUID")],
        done: Annotated[bool, Field(default=True, description="True for done, False for todo")] = True,
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(task_id)
        except ValueError:
            raise InvalidInputError("task_id must be a valid UUID.") from None

        completed = await complete_task(parsed_id, done=done)
        return _serialize_task(completed)

    @mcp.tool(
        name="study_split_task",
        description="Split a parent task into ordered child step tasks. Steps inherit parent course and academic item links.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_split_task(
        task_id: Annotated[str, Field(description="Parent task UUID")],
        steps: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=20, description="List of step objects with 'title', optional 'selected_day', and optional 'estimated_minutes'")],
        replace_existing: Annotated[bool, Field(default=False, description="Whether to replace current child steps")] = False,
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(task_id)
        except ValueError:
            raise InvalidInputError("task_id must be a valid UUID.") from None

        # Validate step shape and coerce ISO date strings before the service writes them.
        parsed_steps = [StepItem.model_validate(step).model_dump(exclude_unset=True) for step in steps]

        parent, created_steps = await split_task(parsed_id, parsed_steps, replace_existing=replace_existing)
        return {
            "parent_task": _serialize_task(parent),
            "steps": [_serialize_task(s) for s in created_steps],
        }

    @mcp.tool(
        name="study_get_today_plan",
        description="Retrieve ordered tasks selected for today and the sum of estimated effort in minutes.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_today_plan(
        day: Annotated[date | None, Field(default=None, description="Defaults to today")] = None,
        timezone: Annotated[str | None, Field(default=None, description="IANA timezone name, e.g. 'America/New_York'")] = None,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        plan = await get_today_plan(day=day, timezone_name=timezone)
        serialized_tasks = [_serialize_task(t) for t in plan.tasks]
        data = {
            "day": plan.day.isoformat(),
            "total_estimated_minutes": plan.total_estimated_minutes,
            "tasks": serialized_tasks,
        }

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- [{'x' if t['status'] == 'done' else ' '}] {t['title']} ({t['estimated_minutes'] or 0}m)" for t in serialized_tasks]
            markdown_summary = f"### Plan for {plan.day.isoformat()} ({plan.total_estimated_minutes} min total)\n" + ("\n".join(lines) if lines else "No tasks scheduled.")

        return format_read_response(data, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_upcoming_plan",
        description="Retrieve upcoming 7 to 14 days of planned work, grouped by day with estimated workload sums.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_upcoming_plan(
        days: Annotated[int, Field(default=7, ge=7, le=14, description="Number of days to retrieve (7-14)")] = 7,
        start_day: Annotated[date | None, Field(default=None, description="Defaults to today")] = None,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        upcoming = await get_upcoming_plan(days=days, start_day=start_day)
        data = {
            "start_day": upcoming.start_day.isoformat(),
            "end_day": upcoming.end_day.isoformat(),
            "days": [
                {
                    "day": d.day.isoformat(),
                    "total_estimated_minutes": d.total_estimated_minutes,
                    "tasks": [_serialize_task(t) for t in d.tasks],
                }
                for d in upcoming.days
            ],
        }

        markdown_summary = None
        if response_format == "markdown":
            lines = []
            for d in data["days"]:
                lines.append(f"**{d['day']}** ({d['total_estimated_minutes']}m, {len(d['tasks'])} tasks):")
                for t in d["tasks"]:
                    lines.append(f"  - [{'x' if t['status'] == 'done' else ' '}] {t['title']} ({t['estimated_minutes'] or 0}m)")
            markdown_summary = f"### Upcoming Plan ({upcoming.start_day.isoformat()} to {upcoming.end_day.isoformat()})\n" + "\n".join(lines)

        return format_read_response(data, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_backlog",
        description="Retrieve unfinished tasks that have no selected work day, ordered by list position.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_backlog(
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        backlog = await get_backlog(limit=limit, offset=offset)
        serialized_tasks = [_serialize_task(t) for t in backlog.tasks]
        extra = {"total_estimated_minutes": backlog.total_estimated_minutes}
        paged = paginate_response(serialized_tasks, limit=limit, offset=offset, has_more=backlog.has_more, extra_fields=extra)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- **{t['title']}** ({t['estimated_minutes'] or 0}m) [{t['status']}]" for t in serialized_tasks]
            markdown_summary = f"### Backlog ({len(serialized_tasks)} items, {backlog.total_estimated_minutes} min)\n" + ("\n".join(lines) if lines else "Backlog is empty.")

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_plan_board",
        description="Retrieve a Kanban board view with columns keyed by selected day plus a backlog column.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_plan_board(
        start_day: Annotated[date | None, Field(default=None, description="Start day for calendar columns (default today)")] = None,
        days: Annotated[int, Field(default=7, ge=7, le=14, description="Number of day columns (7-14)")] = 7,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        board = await get_plan_board(start_day=start_day, days=days)
        data = {
            "columns": [
                {
                    "day": col["day"],
                    "total_estimated_minutes": col["total_estimated_minutes"],
                    "tasks": [_serialize_task(t) for t in col["tasks"]],
                }
                for col in board.columns
            ],
            "backlog": [_serialize_task(t) for t in board.backlog],
        }

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"### Plan Board ({days} Days + Backlog)"]
            for col in data["columns"]:
                lines.append(f"\n#### {col['day']} ({col['total_estimated_minutes']}m)")
                for t in col["tasks"]:
                    lines.append(f"- [{'x' if t['status'] == 'done' else ' '}] {t['title']} ({t['estimated_minutes'] or 0}m)")
            lines.append(f"\n#### Backlog ({len(data['backlog'])} items)")
            for t in data["backlog"]:
                lines.append(f"- {t['title']} ({t['estimated_minutes'] or 0}m)")
            markdown_summary = "\n".join(lines)

        return format_read_response(data, response_format=response_format, markdown_summary=markdown_summary)
