"""Shared pagination envelope and response formatting utilities for MCP tools."""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


def paginate_response(
    items: Sequence[Any],
    limit: int,
    offset: int,
    has_more: bool,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the canonical pagination envelope."""
    response: dict[str, Any] = {
        "items": list(items),
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "next_offset": (offset + len(items)) if has_more else None,
    }
    if extra_fields:
        response.update(extra_fields)
    return response


def format_read_response(
    data: dict[str, Any],
    response_format: str | ResponseFormat = ResponseFormat.JSON,
    markdown_summary: str | None = None,
) -> dict[str, Any]:
    """Format read responses supporting json (default) and markdown modes."""
    fmt = str(response_format).lower()
    if fmt == ResponseFormat.MARKDOWN.value and markdown_summary:
        result = dict(data)
        result["markdown_summary"] = markdown_summary
        return result
    return data
