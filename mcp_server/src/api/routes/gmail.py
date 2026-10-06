"""Local Gmail configuration and browser-based Google authorization endpoints."""

import json
import os
import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from src.api.openapi import openapi_doc
from src.api.schemas import GmailConfigurationRequest, GmailConnectionResponse
from src.connectors.gmail import account_email, authorization_url, exchange_code
from src.services.gmail_connection import (
    connect_gmail_account, get_gmail_connection, save_gmail_configuration,
)

CALLBACK_PATH = "/api/connections/gmail/callback"
STATE_COOKIE = "acadra_gmail_oauth_state"
DEFAULT_REDIRECT_URI = f"http://127.0.0.1:8001{CALLBACK_PATH}"
DEFAULT_WEB_URL = "http://localhost:3000"


def _settings() -> tuple[str, str, str]:
    client_id = os.getenv("ACADRA_GMAIL_CLIENT_ID", "")
    client_secret = os.getenv("ACADRA_GMAIL_CLIENT_SECRET", "")
    redirect_uri = os.getenv("ACADRA_GMAIL_REDIRECT_URI", DEFAULT_REDIRECT_URI)
    if not client_id or client_id == "your_client_id" or not client_secret or client_secret == "your_client_secret":
        raise RuntimeError("Google OAuth client credentials are not configured.")
    if not redirect_uri.endswith(CALLBACK_PATH):
        raise RuntimeError("The Gmail redirect URI must end with the local callback path.")
    return client_id, client_secret, redirect_uri


def _view(connection) -> GmailConnectionResponse:
    return GmailConnectionResponse(
        connection_id=connection.id if connection else None,
        account_email=connection.external_account_id if connection else None,
        allowed_senders=connection.allowed_senders if connection else [],
        status=connection.status if connection else "not_configured",
        oauth_configured=bool(
            os.getenv("ACADRA_GMAIL_CLIENT_ID") not in {None, "", "your_client_id"}
            and os.getenv("ACADRA_GMAIL_CLIENT_SECRET") not in {None, "", "your_client_secret"}
        ),
    )


@openapi_doc(summary="Read Gmail connection and allowed senders", response_model=GmailConnectionResponse)
async def get_gmail_configuration(request: Request) -> JSONResponse:
    try:
        connection = await get_gmail_connection()
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Gmail configuration storage is unavailable."}, status_code=503)
    return JSONResponse(_view(connection).model_dump(mode="json"))


@openapi_doc(
    summary="Save exact sender addresses Acadra may read",
    request_model=GmailConfigurationRequest, response_model=GmailConnectionResponse,
    responses={"200": "Updated", "201": "Created", "422": "Invalid senders", "503": "Storage unavailable"},
)
async def put_gmail_configuration(request: Request) -> JSONResponse:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return JSONResponse({"error": "Content-Type must be application/json."}, status_code=415)
    body = await request.body()
    if len(body) > 16 * 1024:
        return JSONResponse({"error": "Configuration is too large."}, status_code=413)
    try:
        submitted = GmailConfigurationRequest.model_validate(json.loads(body))
    except (ValueError, ValidationError):
        return JSONResponse({"error": "Enter 1–50 valid sender email addresses."}, status_code=422)
    try:
        connection, created = await save_gmail_configuration(submitted.allowed_senders)
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Gmail configuration storage is unavailable."}, status_code=503)
    return JSONResponse(_view(connection).model_dump(mode="json"), status_code=201 if created else 200)


@openapi_doc(summary="Start local Google OAuth for the configured Gmail account")
async def authorize_gmail(request: Request):
    try:
        client_id, _, redirect_uri = _settings()
        connection = await get_gmail_connection()
    except (RuntimeError, SQLAlchemyError):
        return JSONResponse({"error": "Gmail setup is unavailable. Check backend configuration."}, status_code=503)
    if connection is None or not connection.allowed_senders:
        return JSONResponse({"error": "Save allowed senders before connecting Gmail."}, status_code=422)
    nonce = secrets.token_urlsafe(32)
    state = f"{connection.id}:{nonce}"
    response = RedirectResponse(authorization_url(client_id, redirect_uri, state), status_code=303)
    response.set_cookie(
        STATE_COOKIE, state, max_age=600, httponly=True,
        samesite="lax", secure=redirect_uri.startswith("https://"),
    )
    return response


def _web_redirect(result: str) -> RedirectResponse:
    web_url = os.getenv("ACADRA_WEB_URL", DEFAULT_WEB_URL).rstrip("/")
    response = RedirectResponse(f"{web_url}/gmail?{urlencode({'connection': result})}", status_code=303)
    response.delete_cookie(STATE_COOKIE)
    return response


@openapi_doc(summary="Complete local Google OAuth callback")
async def gmail_callback(request: Request):
    state = request.query_params.get("state", "")
    saved_state = request.cookies.get(STATE_COOKIE, "")
    if not state or not saved_state or not secrets.compare_digest(state, saved_state):
        return _web_redirect("invalid_state")
    if request.query_params.get("error"):
        return _web_redirect("denied")
    code = request.query_params.get("code", "")
    if not code or len(code) > 4096:
        return _web_redirect("invalid_code")
    try:
        connection_id = UUID(state.split(":", 1)[0])
        client_id, client_secret, redirect_uri = _settings()
        access_token, refresh_token = await exchange_code(
            code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
        )
        email = await account_email(access_token)
        await connect_gmail_account(connection_id, email, refresh_token)
    except (ValueError, RuntimeError, SQLAlchemyError, httpx.HTTPError):
        return _web_redirect("failed")
    return _web_redirect("connected")
