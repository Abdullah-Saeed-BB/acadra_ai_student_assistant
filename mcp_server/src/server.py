"""Bare MCP server entry point; tools and resources will be added later."""

import argparse

from mcp.server.fastmcp import FastMCP

from .config import Settings


settings = Settings.from_env()
mcp = FastMCP("study_planner_mcp", host=settings.host, port=settings.port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the study planner MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=settings.transport,
        help="MCP transport to use (default: STUDY_MCP_TRANSPORT or stdio)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
