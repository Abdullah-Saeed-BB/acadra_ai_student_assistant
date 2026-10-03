"""HTTP boundary for student-pasted plain text."""

import json

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.openapi import openapi_doc
from src.api.schemas import ManualTextRequest, ManualTextResponse
from src.connectors.manual import prepare_manual_text
from src.services.manual_text import save_manual_text

MAX_REQUEST_BYTES = 512 * 1024


@openapi_doc(
    summary="Add or replace manual text source",
    description="Accepts plain text and optional title/source_document_id to store source revisions.",
    request_model=ManualTextRequest,
    response_model=ManualTextResponse,
    responses={
        "200": "Source revision updated",
        "201": "New source created",
        "400": "Invalid payload or formatting",
        "415": "Unsupported media type",
        "422": "Validation error",
        "503": "Storage unavailable",
    },
)
async def add_manual_text(request: Request) -> JSONResponse:

    """Create a manual source or replace one by its returned ID."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return JSONResponse({"error": "Content-Type must be application/json."}, status_code=415)

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_REQUEST_BYTES:
            return JSONResponse({"error": "Request body is too large."}, status_code=413)

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"error": "Request body must be valid JSON."}, status_code=400)

    try:
        submitted = ManualTextRequest.model_validate(payload)
        envelope = prepare_manual_text(
            submitted.text,
            title=submitted.title,
            source_document_id=submitted.source_document_id,
        )
    except ValidationError as exc:
        details = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse({"error": "Invalid request.", "details": details}, status_code=422)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    try:
        result = await save_manual_text(envelope)
    except ValueError:
        return JSONResponse({"error": "Manual text source was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Manual text storage is unavailable."}, status_code=503)

    response = ManualTextResponse(
        source_document_id=result.source_document_id,
        source_revision_id=result.source_revision_id,
        revision_no=result.revision_no,
        created_revision=result.created_revision,
    )
    return JSONResponse(
        response.model_dump(mode="json"),
        status_code=201 if submitted.source_document_id is None else 200,
    )
