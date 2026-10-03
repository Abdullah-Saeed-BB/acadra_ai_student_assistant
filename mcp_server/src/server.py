"""MCP entry point; HTTP mode also serves web REST routes."""

import argparse

from mcp.server.fastmcp import FastMCP
import uvicorn

from .config import Settings
from .mcp.tools.manual_text import register as register_manual_text


settings = Settings.from_env()
mcp = FastMCP("study_planner_mcp", host=settings.host, port=settings.port, debug=settings.debug)
register_manual_text(mcp)


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
    )


if __name__ == "__main__":
    main()
