"""MCP entry point; HTTP mode also serves web REST routes."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP
import uvicorn

from .config import Settings
from .mcp.resources.academic_context import register as register_resources
from .mcp.tools.academic_items import register as register_academic_items
from .mcp.tools.changes import register as register_changes
from .mcp.tools.connections import register as register_connections
from .mcp.tools.courses import register as register_courses
from .mcp.tools.manual_text import register as register_manual_text
from .mcp.tools.preferences import register as register_preferences
from .mcp.tools.sources import register as register_sources
from .mcp.tools.tasks import register as register_tasks

settings = Settings.from_env()
mcp = FastMCP(
    "study_planner_mcp",
    host=settings.host,
    port=settings.port,
    debug=settings.debug,
    stateless_http=settings.stateless_http,
    json_response=settings.json_response,
    transport_security=settings.transport_security(),
)

# Register MCP tools
register_manual_text(mcp)
register_academic_items(mcp)
register_changes(mcp)
register_sources(mcp)
register_courses(mcp)
register_tasks(mcp)
register_preferences(mcp)
register_connections(mcp)

# Register MCP read-only resources
register_resources(mcp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the study planner MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=settings.transport,
        help="MCP transport to use (default: STUDY_MCP_TRANSPORT or streamable-http)",
    )
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    uvicorn.run(
        "src.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        access_log=False,
    )


if __name__ == "__main__":
    main()
