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
        clear_preferred_daily_minutes: Annotated[bool, Field(default=False, description="Clear the preferred daily minutes default instead of leaving it unchanged")] = False,
        clear_focus_task_count: Annotated[bool, Field(default=False, description="Clear the focus task count default instead of leaving it unchanged")] = False,
    ) -> dict[str, Any]:
        prefs = await set_preferences(
            preferred_daily_minutes=None if clear_preferred_daily_minutes else preferred_daily_minutes,
            focus_task_count=None if clear_focus_task_count else focus_task_count,
            scope="default",
            clear_preferred_daily_minutes=clear_preferred_daily_minutes,
            clear_focus_task_count=clear_focus_task_count,
        )
        return {
            "preferred_daily_minutes": prefs.preferred_daily_minutes,
            "focus_task_count": prefs.focus_task_count,
            "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
        }
