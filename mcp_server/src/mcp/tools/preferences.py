"""MCP tools for getting and setting student planning preferences."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from src.errors import handle_tool_errors
from src.services.preferences import get_preferences, set_preferences


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="study_get_preferences",
        description="Retrieve the student's planning defaults (preferred daily study minutes and focus task count).",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_get_preferences() -> dict[str, Any]:
        prefs = await get_preferences(scope="default")
        return {
            "preferred_daily_minutes": prefs.preferred_daily_minutes,
            "focus_task_count": prefs.focus_task_count,
            "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
        }

    @mcp.tool(
        name="study_set_preferences",
        description="Save or update the student's planning defaults (daily study minutes and focus task count). Idempotent.",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @handle_tool_errors
    async def study_set_preferences(
        preferred_daily_minutes: Annotated[int | None, Field(default=None, ge=1, le=1440, description="Preferred total daily effort in minutes")] = None,
        focus_task_count: Annotated[int | None, Field(default=None, ge=1, le=20, description="Target focus task count per day")] = None,
    ) -> dict[str, Any]:
        prefs = await set_preferences(
            preferred_daily_minutes=preferred_daily_minutes,
            focus_task_count=focus_task_count,
            scope="default",
        )
        return {
            "preferred_daily_minutes": prefs.preferred_daily_minutes,
            "focus_task_count": prefs.focus_task_count,
            "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
        }
