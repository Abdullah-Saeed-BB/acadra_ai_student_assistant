"""MCP tools for inspecting sources, revisions, and extracted candidates."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors, InvalidInputError, NotFoundError
from src.mcp.responses import format_read_response, paginate_response
from src.services.source_processing import list_latest_source_candidates
from src.services.sources import get_source_detail, list_sources


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_list_sources",
        description="List saved source documents with their latest revision number, observation time, and review status.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_list_sources(
        source_type: Annotated[Literal["text", "html", "pdf", "gmail"] | None, Field(default=None, description="Optional source type filter")] = None,
        limit: Annotated[int, Field(default=20, ge=1, le=100, description="Page limit (1-100)")] = 20,
        offset: Annotated[int, Field(default=0, ge=0, description="Page offset")] = 0,
        response_format: Annotated[Literal["json", "markdown"], Field(default="json", description="Response representation")] = "json",
    ) -> dict[str, Any]:
        page = await list_sources(source_type=source_type, limit=limit, offset=offset)
        serialized_items = [
            {
                "id": str(item.id),
                "source_type": item.source_type,
                "title": item.title,
                "original_ref": item.original_ref,
                "course_hint": item.course_hint,
                "latest_revision_no": item.latest_revision_no,
                "observed_at": item.observed_at.isoformat() if item.observed_at else None,
                "has_review_candidates": item.has_review_candidates,
                "last_change_at": item.last_change_at.isoformat() if item.last_change_at else None,
            }
            for item in page.items
        ]
        paged = paginate_response(serialized_items, limit=limit, offset=offset, has_more=page.has_more)

        markdown_summary = None
        if response_format == "markdown":
            lines = [f"- **{i['title'] or i['original_ref'] or 'Untitled'}** ({i['source_type']}) — Rev {i['latest_revision_no']}" for i in serialized_items]
            markdown_summary = f"### Sources ({len(serialized_items)})\n" + "\n".join(lines)

        return format_read_response(paged, response_format=response_format, markdown_summary=markdown_summary)

    @mcp.tool(
        name="study_get_source_detail",
        description="Retrieve metadata, all content revisions, and produced academic items for a source document.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_source_detail(
        source_document_id: Annotated[str, Field(description="Source document UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(source_document_id)
        except ValueError:
            raise InvalidInputError("source_document_id must be a valid UUID.") from None

        detail = await get_source_detail(parsed_id)
        return {
            "id": str(detail.id),
            "source_type": detail.source_type,
            "title": detail.title,
            "original_ref": detail.original_ref,
            "course_hint": detail.course_hint,
            "revisions": [
                {
                    "id": str(rev.id),
                    "revision_no": rev.revision_no,
                    "content_hash": rev.content_hash,
                    "observed_at": rev.observed_at.isoformat(),
                    "source_updated_at": rev.source_updated_at.isoformat() if rev.source_updated_at else None,
                }
                for rev in detail.revisions
            ],
            "academic_items": detail.academic_items,
            "has_review_candidates": detail.has_review_candidates,
            "last_change_at": detail.last_change_at.isoformat() if detail.last_change_at else None,
        }

    @mcp.tool(
        name="study_list_source_candidates",
        description="Read candidates extracted from the source document's latest revision (including withheld/uncertain items).",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_list_source_candidates(
        source_document_id: Annotated[str, Field(description="Source document UUID")],
    ) -> dict[str, Any]:
        try:
            parsed_id = UUID(source_document_id)
        except ValueError:
            raise InvalidInputError("source_document_id must be a valid UUID.") from None

        candidates = await list_latest_source_candidates(parsed_id)
        if candidates is None:
            raise NotFoundError(f"Source document {source_document_id} was not found.")

        return {
            "source_document_id": str(parsed_id),
            "candidates": [
                {
                    "id": str(c.id),
                    "source_revision_id": str(c.source_revision_id),
                    "academic_item_id": str(c.academic_item_id) if c.academic_item_id else None,
                    "evidence": c.evidence,
                    "review_reasons": c.review_reasons,
                    "date_facts": c.date_facts,
                }
                for c in candidates
            ],
        }
