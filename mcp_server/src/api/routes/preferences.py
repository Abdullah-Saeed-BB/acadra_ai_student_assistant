"""HTTP boundary for reading and writing planning preferences."""

from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.requests import read_json_body, validation_error_response
from src.api.schemas import PlanningPreferencesRequest, PlanningPreferencesResponse
from src.errors import InvalidInputError
from src.services.preferences import get_preferences, set_preferences


async def get_preferences_route(request: Request) -> JSONResponse:
    try:
        prefs = await get_preferences(scope="default")
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Preference storage is unavailable."}, status_code=503)

    response = PlanningPreferencesResponse(
        preferred_daily_minutes=prefs.preferred_daily_minutes,
        focus_task_count=prefs.focus_task_count,
        updated_at=prefs.updated_at,
    )
    return JSONResponse(response.model_dump(mode="json"))


async def put_preferences_route(request: Request) -> JSONResponse:
    payload, error = await read_json_body(request)
    if error is not None:
        return error
    try:
        submitted = PlanningPreferencesRequest.model_validate(payload)
    except ValidationError as exc:
        return validation_error_response(exc, "Invalid request.")

    try:
        prefs = await set_preferences(
            preferred_daily_minutes=None if submitted.clear_preferred_daily_minutes else submitted.preferred_daily_minutes,
            focus_task_count=None if submitted.clear_focus_task_count else submitted.focus_task_count,
            scope="default",
            clear_preferred_daily_minutes=submitted.clear_preferred_daily_minutes,
            clear_focus_task_count=submitted.clear_focus_task_count,
        )
    except InvalidInputError as exc:
        return JSONResponse({"error": exc.message}, status_code=422)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Preference storage is unavailable."}, status_code=503)

    response = PlanningPreferencesResponse(
        preferred_daily_minutes=prefs.preferred_daily_minutes,
        focus_task_count=prefs.focus_task_count,
        updated_at=prefs.updated_at,
    )
    return JSONResponse(response.model_dump(mode="json"))