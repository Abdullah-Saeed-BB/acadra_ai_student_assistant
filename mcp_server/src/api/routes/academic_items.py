"""HTTP boundary for querying saved academic items."""

from pydantic import ValidationError
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.schemas import AcademicItemEvidenceResponse, AcademicItemListQuery, AcademicItemListResponse, AcademicItemResponse
from src.services.academic_items import AcademicItemFilters, get_academic_item_evidence, list_academic_items


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
        details = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse({"error": "Invalid query.", "details": details}, status_code=422)

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
    summary="Get an academic item's source evidence and review reasons",
    response_model=AcademicItemEvidenceResponse,
    responses={"200": "Source evidence", "404": "No source evidence", "503": "Storage unavailable"},
)
async def get_item_evidence(request: Request) -> JSONResponse:
    try:
        item_id = UUID(request.path_params["item_id"])
    except ValueError:
        return JSONResponse({"error": "Invalid academic item ID."}, status_code=422)
    try:
        evidence = await get_academic_item_evidence(item_id)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Academic item storage is unavailable."}, status_code=503)
    if evidence is None:
        return JSONResponse({"error": "Academic item evidence was not found."}, status_code=404)
    response = AcademicItemEvidenceResponse.model_validate(evidence)
    return JSONResponse(response.model_dump(mode="json"))
