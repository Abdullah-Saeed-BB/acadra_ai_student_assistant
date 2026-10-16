"""HTTP boundary for reading and writing planned tasks and plan views."""

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.schemas import (
    BacklogQuery,
    BacklogResponse,
    DayPlanGroupResponse,
    TaskCreateRequest,
    TaskDeleteResponse,
    TaskDetailResponse,
    TaskListQuery,
    TaskListResponse,
    TaskReorderRequest,
    TaskReorderResponse,
    TaskResponse,
    TaskUpdateRequest,
    TodayPlanQuery,
    TodayPlanResponse,
    UpcomingPlanQuery,
    UpcomingPlanResponse,
)
from src.errors import InvalidInputError, NotFoundError
from src.services.tasks import (
    create_task,
    delete_task,
    get_backlog,
    get_task,
    get_today_plan,
    get_upcoming_plan,
    list_tasks,
    reorder_tasks,
    update_task,
)

MAX_TASK_BODY_BYTES = 64 * 1024


def _validation_error(exc: ValidationError, message: str = "Invalid query.") -> JSONResponse:
    details = [
        {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse({"error": message, "details": details}, status_code=422)


async def _read_json_body(request: Request) -> tuple[object | None, JSONResponse | None]:
    """Read a bounded JSON body, or return the error response to send back."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return None, JSONResponse(
            {"error": "Content-Type must be application/json."}, status_code=415
        )
    body = await request.body()
    if len(body) > MAX_TASK_BODY_BYTES:
        return None, JSONResponse({"error": "Request body is too large."}, status_code=413)
    try:
        return json.loads(body), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JSONResponse(
            {"error": "Request body must be valid JSON."}, status_code=400
        )


def _task_identifier(request: Request) -> tuple[UUID | None, JSONResponse | None]:
    try:
        return UUID(request.path_params["task_id"]), None
    except ValueError:
        return None, JSONResponse({"error": "Invalid task ID."}, status_code=422)


@openapi_doc(
    summary="List planned tasks",
    description=(
        "Returns tasks ordered by selected day (undated last), then list position. "
        "has_selected_day=false returns only Backlog tasks."
    ),
    query_model=TaskListQuery,
    response_model=TaskListResponse,
    responses={
        "200": "Task page",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def list_tasks_route(request: Request) -> JSONResponse:
    try:
        params = TaskListQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return _validation_error(exc)

    try:
        page = await list_tasks(
            status=params.status,
            selected_day=params.selected_day,
            selected_from=params.selected_from,
            selected_to=params.selected_to,
            has_selected_day=params.has_selected_day,
            parent_task_id=params.parent_task_id,
            academic_item_id=params.academic_item_id,
            course_id=params.course_id,
            tag=params.tag,
            limit=params.limit,
            offset=params.offset,
        )
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TaskListResponse(
        items=[TaskResponse.model_validate(item) for item in page.items],
        limit=params.limit,
        offset=params.offset,
        has_more=page.has_more,
        next_offset=params.offset + len(page.items) if page.has_more else None,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Create a task",
    description=(
        "Create a student task or child step. Link it to an academic item, a course, "
        "or a parent task; omit selected_day to place it in the Backlog."
    ),
    request_model=TaskCreateRequest,
    response_model=TaskResponse,
    responses={
        "201": "Task created",
        "404": "Linked academic item, course, or parent task not found",
        "413": "Request body too large",
        "415": "Unsupported media type",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def create_task_route(request: Request) -> JSONResponse:
    payload, error = await _read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = TaskCreateRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc, "Invalid request.")

    try:
        task = await create_task(
            title=submitted.title,
            details=submitted.details,
            selected_day=submitted.selected_day,
            estimated_minutes=submitted.estimated_minutes,
            tags=submitted.tags,
            academic_item_id=submitted.academic_item_id,
            course_id=submitted.course_id,
            parent_task_id=submitted.parent_task_id,
        )
    except NotFoundError:
        return JSONResponse(
            {"error": "A linked academic item, course, or parent task was not found."},
            status_code=404,
        )
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TaskResponse.model_validate(task)
    return JSONResponse(response.model_dump(mode="json"), status_code=201)


@openapi_doc(
    summary="Read one task with its steps and progress",
    response_model=TaskDetailResponse,
    responses={"200": "Task detail", "404": "Task not found", "503": "Storage unavailable"},
)
async def get_task_route(request: Request) -> JSONResponse:
    try:
        task_id = UUID(request.path_params["task_id"])
    except ValueError:
        return JSONResponse({"error": "Invalid task ID."}, status_code=422)
    try:
        detail = await get_task(task_id)
    except NotFoundError:
        return JSONResponse({"error": "Task was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)
    response = TaskDetailResponse(
        **TaskResponse.model_validate(detail.task).model_dump(),
        steps=[TaskResponse.model_validate(step) for step in detail.steps],
        progress=detail.progress,
        academic_item=detail.academic_item,
        course=detail.course,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Update a task",
    description=(
        "Partially update a task's fields. Link or unlink an academic item or course "
        "with academic_item_id/course_id (null to unlink) or the clear_* flags."
    ),
    request_model=TaskUpdateRequest,
    response_model=TaskResponse,
    responses={
        "200": "Task updated",
        "404": "Task or a linked record not found",
        "413": "Request body too large",
        "415": "Unsupported media type",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def update_task_route(request: Request) -> JSONResponse:
    task_id, error = _task_identifier(request)
    if error is not None:
        return error
    payload, error = await _read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = TaskUpdateRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc, "Invalid request.")

    provided = submitted.model_dump(exclude_unset=True)

    explicit_item = "academic_item_id" in provided
    item_value = provided.pop("academic_item_id", None)
    clear_academic_item = bool(provided.pop("clear_academic_item", False)) or (
        explicit_item and item_value is None
    )

    explicit_course = "course_id" in provided
    course_value = provided.pop("course_id", None)
    clear_course = bool(provided.pop("clear_course", False)) or (
        explicit_course and course_value is None
    )

    explicit_day = "selected_day" in provided
    day_value = provided.pop("selected_day", None)
    clear_selected_day = bool(provided.pop("clear_selected_day", False)) or (
        explicit_day and day_value is None
    )

    clear_estimated_minutes = bool(provided.pop("clear_estimated_minutes", False))

    try:
        updated = await update_task(
            task_id=task_id,
            title=provided.get("title"),
            details=provided.get("details"),
            status=provided.get("status"),
            selected_day=day_value,
            clear_selected_day=clear_selected_day,
            list_position=provided.get("list_position"),
            estimated_minutes=provided.get("estimated_minutes"),
            clear_estimated_minutes=clear_estimated_minutes,
            tags=provided.get("tags"),
            parent_task_id=provided.get("parent_task_id"),
            academic_item_id=item_value,
            clear_academic_item=clear_academic_item,
            course_id=course_value,
            clear_course=clear_course,
        )
    except NotFoundError:
        return JSONResponse(
            {"error": "The task or one of its linked records was not found."},
            status_code=404,
        )
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TaskResponse.model_validate(updated)
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Delete a task and its steps",
    description=(
        "Remove a task and its child steps. Linked academic items and courses are "
        "kept; the response reports which links the deleted task had."
    ),
    response_model=TaskDeleteResponse,
    responses={"200": "Task deleted", "404": "Task not found", "503": "Storage unavailable"},
)
async def delete_task_route(request: Request) -> JSONResponse:
    task_id, error = _task_identifier(request)
    if error is not None:
        return error
    try:
        deletion = await delete_task(task_id)
    except NotFoundError:
        return JSONResponse({"error": "Task was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TaskDeleteResponse(
        id=deletion.task_id,
        title=deletion.title,
        deleted_steps=deletion.deleted_steps,
        academic_item_id=deletion.academic_item_id,
        course_id=deletion.course_id,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Reorder the tasks on a selected day",
    description=(
        "Rewrite the list positions of the given tasks to match task_ids order. "
        "The tasks are assigned to the given selected_day (null for the Backlog), "
        "so one call reorders one saved list."
    ),
    request_model=TaskReorderRequest,
    response_model=TaskReorderResponse,
    responses={
        "200": "Tasks reordered",
        "404": "A task in the reorder list was not found",
        "413": "Request body too large",
        "415": "Unsupported media type",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def reorder_tasks_route(request: Request) -> JSONResponse:
    payload, error = await _read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = TaskReorderRequest.model_validate(payload)
    except ValidationError as exc:
        return _validation_error(exc, "Invalid request.")

    try:
        updated = await reorder_tasks(
            selected_day=submitted.selected_day,
            task_ids=submitted.task_ids,
        )
    except NotFoundError:
        return JSONResponse(
            {"error": "A task in the reorder list was not found."}, status_code=404
        )
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TaskReorderResponse(
        selected_day=submitted.selected_day,
        tasks=[TaskResponse.model_validate(task) for task in updated],
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Return the Today view",
    description="Tasks whose selected day is today (or the given day), in list order, with total estimated effort.",
    query_model=TodayPlanQuery,
    response_model=TodayPlanResponse,
    responses={"200": "Today plan", "422": "Validation error", "503": "Storage unavailable"},
)
async def get_today_plan_route(request: Request) -> JSONResponse:
    try:
        params = TodayPlanQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return _validation_error(exc)

    try:
        plan = await get_today_plan(day=params.day)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = TodayPlanResponse(
        day=plan.day,
        total_estimated_minutes=plan.total_estimated_minutes,
        tasks=[TaskResponse.model_validate(task) for task in plan.tasks],
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Return the Upcoming view",
    description="Tasks selected for the next days, grouped by day with workload sums.",
    query_model=UpcomingPlanQuery,
    response_model=UpcomingPlanResponse,
    responses={"200": "Upcoming plan", "422": "Validation error", "503": "Storage unavailable"},
)
async def get_upcoming_plan_route(request: Request) -> JSONResponse:
    try:
        params = UpcomingPlanQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return _validation_error(exc)

    try:
        upcoming = await get_upcoming_plan(days=params.days, start_day=params.start_day)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = UpcomingPlanResponse(
        start_day=upcoming.start_day,
        end_day=upcoming.end_day,
        days=[
            DayPlanGroupResponse(
                day=group.day,
                total_estimated_minutes=group.total_estimated_minutes,
                tasks=[TaskResponse.model_validate(task) for task in group.tasks],
            )
            for group in upcoming.days
        ],
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Return the Backlog view",
    description="Unfinished tasks with no selected day, ordered by list position.",
    query_model=BacklogQuery,
    response_model=BacklogResponse,
    responses={"200": "Backlog", "422": "Validation error", "503": "Storage unavailable"},
)
async def get_backlog_route(request: Request) -> JSONResponse:
    try:
        params = BacklogQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return _validation_error(exc)

    try:
        backlog = await get_backlog(limit=params.limit, offset=params.offset)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Task storage is unavailable."}, status_code=503)

    response = BacklogResponse(
        tasks=[TaskResponse.model_validate(task) for task in backlog.tasks],
        total_estimated_minutes=backlog.total_estimated_minutes,
        limit=params.limit,
        offset=params.offset,
        has_more=backlog.has_more,
        next_offset=params.offset + len(backlog.tasks) if backlog.has_more else None,
    )
    return JSONResponse(response.model_dump(mode="json"))
