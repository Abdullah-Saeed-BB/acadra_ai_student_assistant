"""MCP write tool for plain-text manual sources."""

from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy.exc import SQLAlchemyError

from src.connectors.manual import prepare_manual_text
from src.services.manual_text import save_manual_text


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_add_manual_text",
        description=(
            "Save student-pasted plain text as a source. Omit source_document_id to "
            "create a new source; provide a previously returned ID to replace it. "
            "This stores source revisions only; academic fact extraction is not yet enabled."
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
        except SQLAlchemyError:
            raise RuntimeError("Could not save manual text.") from None
        return {
            "source_document_id": str(result.source_document_id),
            "source_revision_id": str(result.source_revision_id),
            "revision_no": result.revision_no,
            "created_revision": result.created_revision,
        }
