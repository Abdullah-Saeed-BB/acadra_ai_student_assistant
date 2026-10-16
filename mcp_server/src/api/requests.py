"""Shared request parsing helpers for the REST boundary."""

from __future__ import annotations

import json
from uuid import UUID

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_JSON_BODY_BYTES = 64 * 1024


def validation_error_response(
    exc: ValidationError, message: str = "Invalid request."
) -> JSONResponse:
    """Turn a Pydantic validation error into a 422 response with field details."""
    details = [
        {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse({"error": message, "details": details}, status_code=422)


async def read_json_body(
    request: Request, max_bytes: int = MAX_JSON_BODY_BYTES
) -> tuple[object | None, JSONResponse | None]:
    """Read a bounded JSON body, or return the error response to send back."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return None, JSONResponse(
            {"error": "Content-Type must be application/json."}, status_code=415
        )
    body = await request.body()
    if len(body) > max_bytes:
        return None, JSONResponse({"error": "Request body is too large."}, status_code=413)
    try:
        return json.loads(body), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JSONResponse(
            {"error": "Request body must be valid JSON."}, status_code=400
        )


def path_uuid(request: Request, name: str, message: str) -> tuple[UUID | None, JSONResponse | None]:
    """Parse a UUID path parameter, or return a 422 response."""
    try:
        return UUID(request.path_params[name]), None
    except ValueError:
        return None, JSONResponse({"error": message}, status_code=422)
