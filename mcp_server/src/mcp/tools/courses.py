"""MCP tools for courses and course-grouped academic items."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors, InvalidInputError
from src.mcp.responses import format_read_response, paginate_response
from src.services.courses import get_course, list_courses


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_list_courses",
        description="List registered courses with academic item counts, ordered alphabetically by name.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_list_courses(
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        page = await list_courses(limit=limit, offset=offset)
        serialized_items = [
            {
                "id": str(item.id),
                "code": item.code,
                "name": item.name,
                "term": item.term,
                "item_count": item.item_count,
                "created_at": item.created_at.isoformat(),
            }
            for item in page.items
        ]
        paged = paginate_response(serialized_items, limit=limit, offset=offset, has_more=page.has_more)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- **{i['name']}** ({i['code'] or 'No code'}): {i['item_count']} items" for i in serialized_items]
            markdown_summary = f"### Courses ({len(serialized_items)})\n" + "\n".join(lines)

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_course",
        description="Retrieve a single course and its academic items ordered by due date.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_course(
        course_id: Annotated[str, Field(description="Course UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(course_id)
        except ValueError:
            raise InvalidInputError("course_id must be a valid UUID.") from None

        detail = await get_course(parsed_id)
        return {
            "id": str(detail.id),
            "code": detail.code,
            "name": detail.name,
            "term": detail.term,
            "created_at": detail.created_at.isoformat(),
            "academic_items": detail.academic_items,
        }
