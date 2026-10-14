"""MCP tools for academic items change feed."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors, InvalidInputError
from src.mcp.responses import format_read_response, paginate_response
from src.services.changes import get_changes_since


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_get_changes_since",
        description="Append-only change feed from academic_item_changes with item title and item_type context.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_changes_since(
        since: Annotated[datetime | None, Field(default=None, description="Changes recorded after this instant (timezone-aware)")] = None,
        item_type: Annotated[Literal["assignment", "announcement", "reading", "event"] | None, Field(default=None, description="Optional academic item type filter")] = None,
        course_id: Annotated[str | None, Field(default=None, description="Optional course UUID filter")] = None,
        change_kind: Annotated[Literal["created", "edited"] | None, Field(default=None, description="Optional change kind")] = None,
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        parsed_course_id = None
        if course_id:
            try:
                parsed_course_id = UUID(course_id)
            except ValueError:
                raise InvalidInputError("course_id must be a valid UUID.") from None

        page = await get_changes_since(
            since=since,
            item_type=item_type,
            course_id=parsed_course_id,
            change_kind=change_kind,
            limit=limit,
            offset=offset,
        )

        serialized_items = [
            {
                "id": str(item.id),
                "academic_item_id": str(item.academic_item_id),
                "source_revision_id": str(item.source_revision_id) if item.source_revision_id else None,
                "origin": item.origin,
                "change_kind": item.change_kind,
                "before_values": item.before_values,
                "after_values": item.after_values,
                "recorded_at": item.recorded_at.isoformat(),
                "title": item.title,
                "item_type": item.item_type,
            }
            for item in page.items
        ]

        paged = paginate_response(serialized_items, limit=limit, offset=offset, has_more=page.has_more)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- **{i['title']}** [{i['change_kind'].upper()}] by {i['origin']} at {i['recorded_at']}" for i in serialized_items]
            markdown_summary = f"### Recent Changes ({len(serialized_items)})\n" + "\n".join(lines)

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)
