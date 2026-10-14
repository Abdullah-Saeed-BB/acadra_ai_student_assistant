"""MCP operator tools for external source connections (Gmail)."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.connectors.gmail import normalize_allowed_senders
from src.errors import handle_tool_errors, InvalidInputError
from src.services.gmail_connection import get_gmail_connection, save_gmail_configuration


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_get_gmail_connection",
        description="Read Gmail ingestion connection status and configured sender allowlist.",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_gmail_connection() -> dict[str, Any]:
        connection = await get_gmail_connection()
        if connection is None:
            return {
                "connection_id": None,
                "status": "not_configured",
                "account_email": None,
                "allowed_senders": [],
                "last_synced_at": None,
            }

        return {
            "connection_id": str(connection.id),
            "status": connection.status,
            "account_email": connection.external_account_id,
            "allowed_senders": connection.allowed_senders or [],
            "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
        }

    @mcp.tool(
        name="study_set_gmail_senders",
        description="Configure or replace the allowed Gmail senders list (1 to 50 email addresses, normalized to lowercase).",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    @handle_tool_errors
    async def study_set_gmail_senders(
        allowed_senders: Annotated[list[str], Field(min_length=1, max_length=50, description="List of allowed sender email addresses")],
    ) -> dict[str, Any]:
        try:
            normalized = normalize_allowed_senders(allowed_senders)
        except ValueError as err:
            raise InvalidInputError(str(err)) from None

        connection, created = await save_gmail_configuration(normalized)
        return {
            "connection_id": str(connection.id),
            "created": created,
            "status": connection.status,
            "allowed_senders": connection.allowed_senders,
        }
