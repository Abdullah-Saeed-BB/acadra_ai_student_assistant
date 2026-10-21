"""Run the MCP and REST API servers together in one terminal."""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env", override=False)


def run_mcp() -> None:
    sys.argv = ["mcp-server", "--transport", "streamable-http"]
    from src.server import main

    main()


def run_api() -> None:
    sys.argv = ["api-server"]
    from src.api.app import main

    main()


def main() -> None:
    print("Starting MCP server (streamable-http) and REST API server...")
    mcp_process = multiprocessing.Process(target=run_mcp, name="mcp-server", daemon=False)
    api_process = multiprocessing.Process(target=run_api, name="api-server", daemon=False)

    mcp_process.start()
    api_process.start()

    try:
        while mcp_process.is_alive() and api_process.is_alive():
            mcp_process.join(timeout=0.5)
            api_process.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nStopping servers...")
    finally:
        for process in (mcp_process, api_process):
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)


if __name__ == "__main__":
    main()
