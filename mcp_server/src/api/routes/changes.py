"""HTTP boundary for the academic change feed."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.requests import validation_error_response
from src.api.schemas import ChangeListQuery, ChangeListResponse, ChangeResponse
from src.services.changes import get_changes_since


@openapi_doc(
    summary="List academic item changes",
    description=(
        "Append-only change feed ordered newest first, with the affected item's title "
        "and type. Filter by since, item type, course, or change kind."
    ),
    query_model=ChangeListQuery,
    response_model=ChangeListResponse,
    responses={"200": "Change page", "422": "Validation error", "503": "Storage unavailable"},
)
async def get_changes(request: Request) -> JSONResponse:
    try:
        params = ChangeListQuery.model_validate(dict(request.query_params))
    except ValidationError as exc:
        return validation_error_response(exc, "Invalid query.")

    try:
        page = await get_changes_since(
            since=params.since,
            item_type=params.item_type,
            course_id=params.course_id,
            change_kind=params.change_kind,
            limit=params.limit,
            offset=params.offset,
        )
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Change storage is unavailable."}, status_code=503)

    response = ChangeListResponse(
        items=[ChangeResponse.model_validate(item) for item in page.items],
        limit=params.limit,
        offset=params.offset,
        has_more=page.has_more,
        next_offset=params.offset + len(page.items) if page.has_more else None,
    )
    return JSONResponse(response.model_dump(mode="json"))
