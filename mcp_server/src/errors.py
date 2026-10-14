"""Structured error contracts and error-handling utilities for MCP tools and services."""

from __future__ import annotations

from functools import wraps
import json
import logging
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("study_planner_mcp")


class StudyPlannerError(Exception):
    """Base exception for all domain and MCP tool errors."""

    def __init__(self, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.hint is not None:
            data["hint"] = self.hint
        return {"error": data}


class NotFoundError(StudyPlannerError):
    def __init__(self, message: str = "Resource was not found.", hint: str | None = None) -> None:
        super().__init__("not_found", message, hint)


class InvalidInputError(StudyPlannerError):
    def __init__(self, message: str = "Invalid input parameter.", hint: str | None = None) -> None:
        super().__init__("invalid_input", message, hint)


class NotConfiguredError(StudyPlannerError):
    def __init__(self, message: str = "Service is not configured.", hint: str | None = None) -> None:
        super().__init__("not_configured", message, hint)


class PendingConfigurationError(StudyPlannerError):
    def __init__(self, message: str = "Configuration pending.", hint: str | None = None) -> None:
        super().__init__("pending_configuration", message, hint)


class ScopeChangedError(StudyPlannerError):
    def __init__(self, message: str = "Scope or authorization changed.", hint: str | None = None) -> None:
        super().__init__("scope_changed", message, hint)


class ConflictError(StudyPlannerError):
    def __init__(self, message: str = "Write targets a conflicting state.", hint: str | None = None) -> None:
        super().__init__("conflict", message, hint)


class DatabaseUnavailableError(StudyPlannerError):
    def __init__(
        self,
        message: str = "Database storage is unavailable.",
        hint: str | None = "Retry later.",
    ) -> None:
        super().__init__("db_unavailable", message, hint)


def format_error_payload(code: str, message: str, hint: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if hint:
        payload["hint"] = hint
    return {"error": payload}


def map_exception_to_error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, StudyPlannerError):
        return exc.to_dict()
    if isinstance(exc, SQLAlchemyError):
        return format_error_payload(
            "db_unavailable",
            "Database storage is unavailable.",
            "Retry later.",
        )
    if isinstance(exc, ValueError):
        return format_error_payload(
            "invalid_input",
            str(exc),
            "Correct the argument and retry.",
        )
    return format_error_payload(
        "invalid_input",
        str(exc) or "An unexpected error occurred.",
        "Review tool arguments and system status.",
    )


def handle_tool_errors(func: Callable) -> Callable:
    """Decorator for FastMCP tool functions to safely return formatted errors.

    Uses ``@wraps`` to preserve metadata for FastMCP's input-schema introspection,
    then removes the ``return`` annotation so FastMCP never creates a
    structured-output ``DictModel``. Without a return annotation, FastMCP calls
    ``convert_result`` without validating ``structuredContent``, which lets
    ``CallToolResult`` pass through cleanly on error paths.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            payload = map_exception_to_error_payload(exc)
            return CallToolResult(
                isError=True,
                content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
            )

    # Remove the return annotation so FastMCP skips structured-output wiring.
    # The input annotations (parameters) are preserved by @wraps for schema generation.
    wrapper.__annotations__.pop("return", None)
    return wrapper
