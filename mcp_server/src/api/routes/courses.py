"""HTTP boundary for reading registered courses."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.schemas import CourseListQuery, CourseListResponse, CourseResponse
from src.services.courses import list_courses


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
        details = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse({"error": "Invalid query.", "details": details}, status_code=422)

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
