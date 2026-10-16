"""HTTP boundary for reading and writing registered courses."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.requests import path_uuid, read_json_body, validation_error_response
from src.api.schemas import (
    CourseCreateRequest,
    CourseDeleteResponse,
    CourseDetailResponse,
    CourseItemSummaryResponse,
    CourseListQuery,
    CourseListResponse,
    CourseResponse,
    CourseUpdateRequest,
)
from src.errors import InvalidInputError, NotFoundError
from src.services.courses import (
    create_course,
    delete_course,
    get_course,
    list_courses,
    update_course,
)


@openapi_doc(
    summary="List registered courses",
    description="Returns courses with their academic item counts, ordered by name.",
    query_model=CourseListQuery,
    response_model=CourseListResponse,
    responses={"200": "Course page", "422": "Validation error", "503": "Storage unavailable"},
)
async def get_courses(request: Request) -> JSONResponse:
    try:
        params = CourseListQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return validation_error_response(exc, "Invalid query.")

    try:
        page = await list_courses(limit=params.limit, offset=params.offset)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)

    response = CourseListResponse(
        items=[
            CourseResponse(
                id=item.id,
                code=item.code,
                name=item.name,
                term=item.term,
                item_count=item.item_count,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        limit=params.limit,
        offset=params.offset,
        has_more=page.has_more,
        next_offset=params.offset + len(page.items) if page.has_more else None,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Create a course",
    description="Register a course the student can attach academic items and tasks to.",
    request_model=CourseCreateRequest,
    response_model=CourseResponse,
    responses={"201": "Course created", "413": "Request body too large", "415": "Unsupported media type",
               "422": "Validation error", "503": "Storage unavailable"},
)
async def create_course_route(request: Request) -> JSONResponse:
    payload, error = await read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = CourseCreateRequest.model_validate(payload)
    except ValidationError as exc:
        return validation_error_response(exc)

    try:
        course = await create_course(
            name=submitted.name,
            code=submitted.code,
            term=submitted.term,
        )
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)

    response = CourseResponse(
        id=course.id,
        code=course.code,
        name=course.name,
        term=course.term,
        item_count=0,
        created_at=course.created_at,
    )
    return JSONResponse(response.model_dump(mode="json"), status_code=201)


@openapi_doc(
    summary="Read one course with its academic items",
    response_model=CourseDetailResponse,
    responses={"200": "Course detail", "404": "Course not found", "503": "Storage unavailable"},
)
async def get_course_route(request: Request) -> JSONResponse:
    course_id, error = path_uuid(request, "course_id", "Invalid course ID.")
    if error is not None:
        return error
    try:
        detail = await get_course(course_id)
    except NotFoundError:
        return JSONResponse({"error": "Course was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)

    response = CourseDetailResponse(
        id=detail.id,
        code=detail.code,
        name=detail.name,
        term=detail.term,
        created_at=detail.created_at,
        academic_items=[
            CourseItemSummaryResponse.model_validate(item) for item in detail.academic_items
        ],
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Update a course",
    description="Partially update a course's name, code, or term. Clear code or term with the clear_* flags.",
    request_model=CourseUpdateRequest,
    response_model=CourseResponse,
    responses={"200": "Course updated", "404": "Course not found", "413": "Request body too large",
               "415": "Unsupported media type", "422": "Validation error", "503": "Storage unavailable"},
)
async def update_course_route(request: Request) -> JSONResponse:
    course_id, error = path_uuid(request, "course_id", "Invalid course ID.")
    if error is not None:
        return error
    payload, error = await read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = CourseUpdateRequest.model_validate(payload)
    except ValidationError as exc:
        return validation_error_response(exc)

    provided = submitted.model_dump(exclude_unset=True)

    explicit_code = "code" in provided
    code_value = provided.pop("code", None)
    clear_code = bool(provided.pop("clear_code", False)) or (explicit_code and code_value is None)

    explicit_term = "term" in provided
    term_value = provided.pop("term", None)
    clear_term = bool(provided.pop("clear_term", False)) or (explicit_term and term_value is None)

    try:
        course = await update_course(
            course_id=course_id,
            name=provided.get("name"),
            code=code_value,
            clear_code=clear_code,
            term=term_value,
            clear_term=clear_term,
        )
    except NotFoundError:
        return JSONResponse({"error": "Course was not found."}, status_code=404)
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)

    # Recompute the item count so the response matches the list shape.
    try:
        detail = await get_course(course_id)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)
    response = CourseResponse(
        id=course.id,
        code=course.code,
        name=course.name,
        term=course.term,
        item_count=len(detail.academic_items),
        created_at=course.created_at,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Delete a course",
    description="Remove a course. Its academic items and tasks are kept and unlinked.",
    response_model=CourseDeleteResponse,
    responses={"200": "Course deleted", "404": "Course not found", "503": "Storage unavailable"},
)
async def delete_course_route(request: Request) -> JSONResponse:
    course_id, error = path_uuid(request, "course_id", "Invalid course ID.")
    if error is not None:
        return error
    try:
        deletion = await delete_course(course_id)
    except NotFoundError:
        return JSONResponse({"error": "Course was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Course storage is unavailable."}, status_code=503)

    response = CourseDeleteResponse(
        id=deletion.id,
        name=deletion.name,
        unlinked_items=deletion.unlinked_items,
        unlinked_tasks=deletion.unlinked_tasks,
    )
    return JSONResponse(response.model_dump(mode="json"))
