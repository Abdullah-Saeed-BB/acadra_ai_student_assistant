"""HTTP boundary for querying and managing saved academic items."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.requests import path_uuid, read_json_body, validation_error_response
from src.api.schemas import (
    AcademicItemCreateRequest,
    AcademicItemDeleteResponse,
    AcademicItemDetailResponse,
    AcademicItemEvidenceResponse,
    AcademicItemListQuery,
    AcademicItemListResponse,
    AcademicItemResponse,
    AcademicItemUpdateRequest,
)
from src.errors import InvalidInputError, NotFoundError
from src.services.academic_items import (
    AcademicItemFilters,
    create_academic_item,
    delete_academic_item,
    get_academic_item,
    get_academic_item_evidence,
    list_academic_items,
    update_academic_item,
)


@openapi_doc(
    summary="List academic items",
    description=(
        "Returns saved academic items in due-date order, with undated items last. "
        "due_from is inclusive and due_before is exclusive; both require a time zone."
    ),
    query_model=AcademicItemListQuery,
    response_model=AcademicItemListResponse,
    responses={
        "200": "Academic item page",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def get_academic_items(request: Request) -> JSONResponse:
    try:
        params = AcademicItemListQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return validation_error_response(exc, "Invalid query.")

    try:
        page = await list_academic_items(AcademicItemFilters(**params.model_dump()))
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)

    response = AcademicItemListResponse(
        items=[AcademicItemResponse.model_validate(item) for item in page.items],
        limit=params.limit,
        offset=params.offset,
        has_more=page.has_more,
        next_offset=params.offset + len(page.items) if page.has_more else None,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Create an academic item by hand",
    description=(
        "Record an assignment, announcement, reading, or event without a source. "
        "Manual items are marked verified and appear in the change feed."
    ),
    request_model=AcademicItemCreateRequest,
    response_model=AcademicItemResponse,
    responses={"201": "Academic item created", "404": "Linked course not found",
               "413": "Request body too large", "415": "Unsupported media type",
               "422": "Validation error", "503": "Storage unavailable"},
)
async def create_academic_item_route(request: Request) -> JSONResponse:
    payload, error = await read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = AcademicItemCreateRequest.model_validate(payload)
    except ValidationError as exc:
        return validation_error_response(exc)

    try:
        item = await create_academic_item(
            item_type=submitted.item_type,
            title=submitted.title,
            details=submitted.details,
            course_id=submitted.course_id,
            starts_at=submitted.starts_at,
            due_at=submitted.due_at,
            grade_weight_percent=submitted.grade_weight_percent,
            late_penalty=submitted.late_penalty,
        )
    except NotFoundError:
        return JSONResponse({"error": "The linked course was not found."}, status_code=404)
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)

    response = AcademicItemResponse.model_validate(item)
    return JSONResponse(response.model_dump(mode="json"), status_code=201)


@openapi_doc(
    summary="Read one academic item",
    response_model=AcademicItemDetailResponse,
    responses={"200": "Academic item detail", "404": "Academic item not found", "503": "Storage unavailable"},
)
async def get_academic_item_route(request: Request) -> JSONResponse:
    item_id, error = path_uuid(request, "item_id", "Invalid academic item ID.")
    if error is not None:
        return error
    try:
        detail = await get_academic_item(item_id)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)
    if detail is None:
        return JSONResponse({"error": "Academic item was not found."}, status_code=404)

    response = AcademicItemDetailResponse(
        **AcademicItemResponse.model_validate(detail.item).model_dump(),
        course=(
            {
                "id": detail.course.id,
                "code": detail.course.code,
                "name": detail.course.name,
                "term": detail.course.term,
            }
            if detail.course
            else None
        ),
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Update an academic item",
    description=(
        "Partially update an academic item's fields. Clear nullable fields with the "
        "clear_* flags; the edit is recorded as a change event."
    ),
    request_model=AcademicItemUpdateRequest,
    response_model=AcademicItemResponse,
    responses={"200": "Academic item updated", "404": "Academic item or linked course not found",
               "413": "Request body too large", "415": "Unsupported media type",
               "422": "Validation error", "503": "Storage unavailable"},
)
async def update_academic_item_route(request: Request) -> JSONResponse:
    item_id, error = path_uuid(request, "item_id", "Invalid academic item ID.")
    if error is not None:
        return error
    payload, error = await read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = AcademicItemUpdateRequest.model_validate(payload)
    except ValidationError as exc:
        return validation_error_response(exc)

    provided = submitted.model_dump(exclude_unset=True)

    explicit_course = "course_id" in provided
    course_value = provided.pop("course_id", None)
    clear_course = bool(provided.pop("clear_course", False)) or (explicit_course and course_value is None)

    explicit_details = "details" in provided
    details_value = provided.pop("details", None)
    clear_details = bool(provided.pop("clear_details", False)) or (explicit_details and details_value is None)

    explicit_starts = "starts_at" in provided
    starts_value = provided.pop("starts_at", None)
    clear_starts = bool(provided.pop("clear_starts_at", False)) or (explicit_starts and starts_value is None)

    explicit_due = "due_at" in provided
    due_value = provided.pop("due_at", None)
    clear_due = bool(provided.pop("clear_due_at", False)) or (explicit_due and due_value is None)

    explicit_weight = "grade_weight_percent" in provided
    weight_value = provided.pop("grade_weight_percent", None)
    clear_weight = bool(provided.pop("clear_grade_weight", False)) or (
        explicit_weight and weight_value is None
    )

    explicit_penalty = "late_penalty" in provided
    penalty_value = provided.pop("late_penalty", None)
    clear_penalty = bool(provided.pop("clear_late_penalty", False)) or (
        explicit_penalty and penalty_value is None
    )

    try:
        item, _ = await update_academic_item(
            item_id=item_id,
            item_type=provided.get("item_type"),
            title=provided.get("title"),
            details=details_value,
            clear_details=clear_details,
            course_id=course_value,
            clear_course=clear_course,
            starts_at=starts_value,
            clear_starts_at=clear_starts,
            due_at=due_value,
            clear_due_at=clear_due,
            grade_weight_percent=weight_value,
            clear_grade_weight=clear_weight,
            late_penalty=penalty_value,
            clear_late_penalty=clear_penalty,
            review_state=provided.get("review_state"),
        )
    except NotFoundError:
        return JSONResponse(
            {"error": "The academic item or its linked course was not found."},
            status_code=404,
        )
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)

    response = AcademicItemResponse.model_validate(item)
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Delete an academic item",
    description=(
        "Remove an academic item. Linked tasks are kept and unlinked; the item's "
        "source evidence links and change history are removed with it."
    ),
    response_model=AcademicItemDeleteResponse,
    responses={"200": "Academic item deleted", "404": "Academic item not found", "503": "Storage unavailable"},
)
async def delete_academic_item_route(request: Request) -> JSONResponse:
    item_id, error = path_uuid(request, "item_id", "Invalid academic item ID.")
    if error is not None:
        return error
    try:
        deletion = await delete_academic_item(item_id)
    except NotFoundError:
        return JSONResponse({"error": "Academic item was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)

    response = AcademicItemDeleteResponse(
        id=deletion.id,
        title=deletion.title,
        course_id=deletion.course_id,
        unlinked_tasks=deletion.unlinked_tasks,
        removed_source_links=deletion.removed_source_links,
    )
    return JSONResponse(response.model_dump(mode="json"))


@openapi_doc(
    summary="Get an academic item's source evidence and review reasons",
    response_model=AcademicItemEvidenceResponse,
    responses={"200": "Source evidence", "404": "No source evidence", "503": "Storage unavailable"},
)
async def get_item_evidence(request: Request) -> JSONResponse:
    item_id, error = path_uuid(request, "item_id", "Invalid academic item ID.")
    if error is not None:
        return error
    try:
        evidence = await get_academic_item_evidence(item_id)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)
    if evidence is None:
        return JSONResponse({"error": "Academic item evidence was not found."}, status_code=404)
    response = AcademicItemEvidenceResponse.model_validate(evidence)
    return JSONResponse(response.model_dump(mode="json"))
