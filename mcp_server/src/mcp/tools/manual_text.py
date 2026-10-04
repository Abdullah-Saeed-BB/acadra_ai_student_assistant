"""MCP write tool for plain-text manual sources."""

from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError

from src.connectors.manual import prepare_manual_text
from src.services.manual_text import save_manual_text
from src.services.source_processing import process_source_revision


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_add_manual_text",
        description=(
            "Save student-pasted plain text as a source. Omit source_document_id to "
            "create a new source; provide a previously returned ID to replace it. "
            "The source is versioned, then academic facts are extracted when Groq is configured."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    async def study_add_manual_text(
        text: Annotated[str, Field(max_length=65536)],
        title: Annotated[str | None, Field(max_length=200)] = None,
        source_document_id: Annotated[str | None, Field(max_length=36)] = None,
    ) -> dict[str, str | int | bool]:
        try:
            parsed_id = UUID(source_document_id) if source_document_id else None
        except ValueError:
            raise ValueError("source_document_id must be a UUID.") from None
        envelope = prepare_manual_text(text, title=title, source_document_id=parsed_id)
        try:
            result = await save_manual_text(envelope)
            processing = await process_source_revision(result.source_revision_id)
        except SQLAlchemyError:
            raise RuntimeError("Could not save manual text.") from None
        return {
            "source_document_id": str(result.source_document_id),
            "source_revision_id": str(result.source_revision_id),
            "revision_no": result.revision_no,
            "created_revision": result.created_revision,
            "processing_status": processing.status,
            "academic_item_ids": [str(item_id) for item_id in processing.academic_item_ids],
            "review_count": processing.review_count,
        }
