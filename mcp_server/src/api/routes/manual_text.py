"""HTTP boundary for student-pasted plain text."""

import json
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.datastructures import UploadFile

from src.api.openapi import openapi_doc
from src.api.schemas import ManualTextRequest, ManualTextResponse, SourceCandidateListResponse, SourceCandidateResponse
from src.connectors.manual import ManualFileTooLarge, UnsupportedManualFileType, prepare_manual_file, prepare_manual_text
from src.ingestion.file_text import MAX_PDF_BYTES
from src.services.manual_text import save_manual_source, save_manual_text
from src.services.source_processing import list_latest_source_candidates, process_source_revision

MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BODY_BYTES = MAX_PDF_BYTES + 16 * 1024


@openapi_doc(
    summary="Add or replace manual text source",
    description="Stores plain text revisions and extracts supported academic items with Groq when configured.",
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
        processing = await process_source_revision(result.source_revision_id)
    except ValueError:
        return JSONResponse({"error": "Manual text source was not found."}, status_code=404)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Manual text storage is unavailable."}, status_code=503)

    response = ManualTextResponse(
        source_document_id=result.source_document_id,
        source_revision_id=result.source_revision_id,
        revision_no=result.revision_no,
        created_revision=result.created_revision,
        processing_status=processing.status,
        academic_item_ids=processing.academic_item_ids,
        review_count=processing.review_count,
    )
    return JSONResponse(
        response.model_dump(mode="json"),
        status_code=201 if submitted.source_document_id is None else 200,
    )


@openapi_doc(
    summary="Upload an HTML or PDF academic source",
    description="Multipart upload with file, optional title, and optional source_document_id for replacement.",
    request_body={
        "required": True,
        "content": {"multipart/form-data": {"schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "format": "binary"},
                "title": {"type": "string", "maxLength": 200},
                "source_document_id": {"type": "string", "format": "uuid"},
            },
            "required": ["file"],
        }}},
    },
    response_model=ManualTextResponse,
    responses={"200": "Source revision updated", "201": "New source created", "400": "Malformed multipart form",
               "404": "Source not found", "413": "Upload too large", "415": "Unsupported file type",
               "422": "File has no usable text or invalid input", "503": "Storage unavailable"},
)
async def add_manual_file(request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "multipart/form-data":
        return JSONResponse({"error": "Content-Type must be multipart/form-data."}, status_code=415)

    body_bytes = 0
    original_receive = request.receive

    async def bounded_receive():
        nonlocal body_bytes
        message = await original_receive()
        if message["type"] == "http.request":
            body_bytes += len(message.get("body", b""))
            if body_bytes > MAX_FILE_BODY_BYTES:
                raise ManualFileTooLarge("Upload request body is too large.")
        return message

    bounded_request = Request(request.scope, receive=bounded_receive)
    try:
        async with bounded_request.form(max_files=1, max_fields=2, max_part_size=16 * 1024) as form:
            if set(form.keys()) - {"file", "title", "source_document_id"}:
                return JSONResponse({"error": "Unexpected form field."}, status_code=422)
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                return JSONResponse({"error": "A file upload is required."}, status_code=422)
            title = form.get("title")
            source_id = form.get("source_document_id")
            if title is not None and not isinstance(title, str):
                return JSONResponse({"error": "Title must be text."}, status_code=422)
            if source_id is not None and not isinstance(source_id, str):
                return JSONResponse({"error": "source_document_id must be text."}, status_code=422)
            parsed_id = UUID(source_id) if source_id else None
            data = await upload.read(MAX_PDF_BYTES + 1)
            if len(data) > MAX_PDF_BYTES:
                return JSONResponse({"error": "File must be 5 MiB or smaller."}, status_code=413)
            envelope = await prepare_manual_file(
                data, filename=upload.filename or "", content_type=upload.content_type,
                title=title, source_document_id=parsed_id,
            )
    except UnsupportedManualFileType as exc:
        return JSONResponse({"error": str(exc)}, status_code=415)
    except ManualFileTooLarge as exc:
        return JSONResponse({"error": str(exc)}, status_code=413)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    try:
        result = await save_manual_source(envelope)
        processing = await process_source_revision(result.source_revision_id)
    except ValueError:
        return JSONResponse({"error": "Manual source was not found."}, status_code=404)
    except (OSError, RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Manual source storage is unavailable."}, status_code=503)

    response = ManualTextResponse(
        source_document_id=result.source_document_id,
        source_revision_id=result.source_revision_id,
        revision_no=result.revision_no,
        created_revision=result.created_revision,
        processing_status=processing.status,
        academic_item_ids=processing.academic_item_ids,
        review_count=processing.review_count,
    )
    return JSONResponse(response.model_dump(mode="json"), status_code=201 if parsed_id is None else 200)


@openapi_doc(
    summary="List the latest manual source's extracted candidates",
    response_model=SourceCandidateListResponse,
    responses={"200": "Extracted candidates", "404": "Manual source not found", "503": "Storage unavailable"},
)
async def get_source_candidates(request: Request) -> JSONResponse:
    try:
        document_id = UUID(request.path_params["source_document_id"])
    except ValueError:
        return JSONResponse({"error": "Invalid source document ID."}, status_code=422)
    try:
        candidates = await list_latest_source_candidates(document_id)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Manual source storage is unavailable."}, status_code=503)
    if candidates is None:
        return JSONResponse({"error": "Manual source was not found."}, status_code=404)
    response = SourceCandidateListResponse(
        candidates=[SourceCandidateResponse.model_validate(candidate) for candidate in candidates]
    )
    return JSONResponse(response.model_dump(mode="json"))
