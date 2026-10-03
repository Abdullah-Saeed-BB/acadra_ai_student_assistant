"""Dynamic OpenAPI specification generator for Starlette routes."""

from typing import Any, Callable, Type
from pydantic import BaseModel
from starlette.routing import Route


def openapi_doc(
    *,
    summary: str | None = None,
    description: str | None = None,
    request_model: Type[BaseModel] | None = None,
    query_model: Type[BaseModel] | None = None,
    response_model: Type[BaseModel] | None = None,
    responses: dict[int | str, Any] | None = None,
) -> Callable[[Callable], Callable]:
    """Decorator to attach OpenAPI metadata to a route handler."""

    def decorator(func: Callable) -> Callable:
        setattr(
            func,
            "__openapi__",
            {
                "summary": summary,
                "description": description,
                "request_model": request_model,
                "query_model": query_model,
                "response_model": response_model,
                "responses": responses or {},
            },
        )
        return func

    return decorator


def build_openapi_spec(
    app: Any, title: str = "Study Planner REST API", version: str = "0.1.0"
) -> dict[str, Any]:
    """Dynamically generate an OpenAPI 3.1 spec from registered app.routes."""
    paths: dict[str, dict] = {}
    schemas: dict[str, dict] = {}

    def register_schema(model: Type[BaseModel]) -> str:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema
        return model.__name__

    ignored_prefixes = ("/docs", "/openapi.json", "/mcp")

    for route in getattr(app, "routes", []):
        if not isinstance(route, Route):
            continue

        path = route.path
        if any(path.startswith(prefix) for prefix in ignored_prefixes):
            continue

        endpoint = route.endpoint
        doc = endpoint.__doc__ or ""
        doc_lines = [line.strip() for line in doc.strip().splitlines() if line.strip()]

        meta: dict[str, Any] = getattr(endpoint, "__openapi__", {})

        summary = meta.get("summary") or (
            doc_lines[0] if doc_lines else route.name.replace("_", " ").title()
        )
        description = meta.get("description") or (
            "\n".join(doc_lines[1:]) if len(doc_lines) > 1 else doc
        )

        operations: dict[str, dict] = {}
        for method in route.methods or ["GET"]:
            method_lower = method.lower()
            if method_lower in ("head", "options"):
                continue

            op_responses: dict[str, dict] = {}

            custom_responses = meta.get("responses", {})

            # Attach the response schema to every documented successful status.
            resp_model = meta.get("response_model")
            if resp_model and hasattr(resp_model, "model_json_schema"):
                model_name = register_schema(resp_model)
                success_codes = [
                    str(code)
                    for code in custom_responses
                    if str(code).isdigit() and 200 <= int(code) < 300
                ] or ["200"]
                for code in success_codes:
                    op_responses[code] = {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{model_name}"}
                            }
                        },
                    }

            # Merge custom response definitions
            for code, resp_def in custom_responses.items():
                str_code = str(code)
                if isinstance(resp_def, str):
                    op_responses.setdefault(str_code, {})["description"] = resp_def
                elif isinstance(resp_def, dict):
                    op_responses[str_code] = resp_def

            if not op_responses:
                op_responses["200"] = {"description": "Successful response"}

            op_dict: dict[str, Any] = {
                "summary": summary,
                "description": description,
                "responses": op_responses,
            }

            # Process request model if defined
            req_model = meta.get("request_model")
            if req_model and hasattr(req_model, "model_json_schema"):
                model_name = register_schema(req_model)
                op_dict["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{model_name}"}
                        }
                    },
                }

            query_model = meta.get("query_model")
            if query_model and hasattr(query_model, "model_json_schema"):
                query_schema = query_model.model_json_schema()
                required = set(query_schema.get("required", []))
                op_dict["parameters"] = [
                    {
                        "name": name,
                        "in": "query",
                        "required": name in required,
                        "schema": field_schema,
                    }
                    for name, field_schema in query_schema.get("properties", {}).items()
                ]

            operations[method_lower] = op_dict

        if operations:
            paths[path] = operations

    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": version,
            "description": "Local REST listener for the student web application.",
        },
        "paths": paths,
    }

    if schemas:
        spec["components"] = {"schemas": schemas}

    return spec
