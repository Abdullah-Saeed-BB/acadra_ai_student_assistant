"""Combined MCP and REST ASGI application."""

import argparse
import os
from pathlib import Path
import sys

import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

# Local development settings apply to both the REST route and the mounted MCP app.
# Explicit process environment variables retain priority over .env values.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

from src.api.openapi import build_openapi_spec
from src.api.routes.academic_items import (
    create_academic_item_route,
    delete_academic_item_route,
    get_academic_item_route,
    get_academic_items,
    get_item_evidence,
    update_academic_item_route,
)
from src.api.routes.changes import get_changes
from src.api.routes.courses import (
    create_course_route,
    delete_course_route,
    get_course_route,
    get_courses,
    update_course_route,
)
from src.api.routes.gmail import authorize_gmail, get_gmail_configuration, gmail_callback, put_gmail_configuration
from src.api.routes.manual_text import add_manual_file, add_manual_text, get_source_candidates
from src.api.routes.tasks import (
    create_task_route,
    delete_task_route,
    get_backlog_route,
    get_task_route,
    get_today_plan_route,
    get_upcoming_plan_route,
    list_tasks_route,
    reorder_tasks_route,
    update_task_route,
)
from src.server import mcp

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Study Planner REST API - Swagger UI</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout"
            });
        };
    </script>
</body>
</html>
"""


def is_debug_mode() -> bool:
    return "--debug" in sys.argv or os.getenv("STUDY_API_DEBUG") in ("1", "true", "True")


async def swagger_ui(request: Request) -> Response:
    if not is_debug_mode():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return HTMLResponse(SWAGGER_UI_HTML)


async def openapi_spec(request: Request) -> Response:
    if not is_debug_mode():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    spec = build_openapi_spec(request.app)
    return JSONResponse(spec)



app = mcp.streamable_http_app()
app.add_route("/api/sources/text", add_manual_text, methods=["POST"])
app.add_route("/api/sources/files", add_manual_file, methods=["POST"])
app.add_route("/api/sources/{source_document_id}/candidates", get_source_candidates, methods=["GET"])
app.add_route("/api/sources/text/{source_document_id}/candidates", get_source_candidates, methods=["GET"])
app.add_route("/api/academic-items", get_academic_items, methods=["GET"])
app.add_route("/api/academic-items", create_academic_item_route, methods=["POST"])
app.add_route("/api/academic-items/{item_id}", get_academic_item_route, methods=["GET"])
app.add_route("/api/academic-items/{item_id}", update_academic_item_route, methods=["PATCH"])
app.add_route("/api/academic-items/{item_id}", delete_academic_item_route, methods=["DELETE"])
app.add_route("/api/academic-items/{item_id}/evidence", get_item_evidence, methods=["GET"])
app.add_route("/api/changes", get_changes, methods=["GET"])
app.add_route("/api/courses", get_courses, methods=["GET"])
app.add_route("/api/courses", create_course_route, methods=["POST"])
app.add_route("/api/courses/{course_id}", get_course_route, methods=["GET"])
app.add_route("/api/courses/{course_id}", update_course_route, methods=["PATCH"])
app.add_route("/api/courses/{course_id}", delete_course_route, methods=["DELETE"])
app.add_route("/api/tasks", list_tasks_route, methods=["GET"])
app.add_route("/api/tasks", create_task_route, methods=["POST"])
app.add_route("/api/tasks/reorder", reorder_tasks_route, methods=["POST"])
app.add_route("/api/tasks/{task_id}", get_task_route, methods=["GET"])
app.add_route("/api/tasks/{task_id}", update_task_route, methods=["PATCH"])
app.add_route("/api/tasks/{task_id}", delete_task_route, methods=["DELETE"])
app.add_route("/api/plan/today", get_today_plan_route, methods=["GET"])
app.add_route("/api/plan/upcoming", get_upcoming_plan_route, methods=["GET"])
app.add_route("/api/plan/backlog", get_backlog_route, methods=["GET"])
app.add_route("/api/connections/gmail", get_gmail_configuration, methods=["GET"])
app.add_route("/api/connections/gmail", put_gmail_configuration, methods=["PUT"])
app.add_route("/api/connections/gmail/authorize", authorize_gmail, methods=["GET"])
app.add_route("/api/connections/gmail/callback", gmail_callback, methods=["GET"])
app.add_route("/docs", swagger_ui, methods=["GET"])
app.add_route("/openapi.json", openapi_spec, methods=["GET"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local study planner REST API.")
    parser.add_argument("--port", type=int, default=8001, help="Loopback port (default: 8001)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.debug:
        os.environ["STUDY_API_DEBUG"] = "1"
    app_target = "src.api.app:app" if args.debug else app
    uvicorn.run(app_target, host="127.0.0.1", port=args.port, reload=args.debug, access_log=False)


if __name__ == "__main__":
    main()
