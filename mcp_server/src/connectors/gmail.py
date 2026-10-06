"""Gmail OAuth and sender-scope preparation; message fetching comes later."""

import re
from urllib.parse import urlencode

import httpx

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
_ADDRESS = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$")


def normalize_allowed_senders(values: list[str]) -> list[str]:
    """Accept exact addresses only; no domains, wildcards, or empty scope."""
    if not 1 <= len(values) <= 50:
        raise ValueError("Enter between 1 and 50 sender email addresses.")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Every sender must be an email address.")
        address = value.strip().lower()
        if len(address) > 254 or not _ADDRESS.fullmatch(address) or ".." in address or "*" in address:
            raise ValueError(f"Invalid sender email address: {value[:80]!r}.")
        if address not in normalized:
            normalized.append(address)
    return normalized


def authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    return GOOGLE_AUTH_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })


async def exchange_code(
    code: str, *, client_id: str, client_secret: str, redirect_uri: str,
) -> tuple[str, str]:
    """Return access and refresh tokens without exposing provider error bodies."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
    if response.status_code != 200:
        raise ValueError("Google did not complete authorization. Try connecting again.")
    payload = response.json()
    access_token, refresh_token = payload.get("access_token"), payload.get("refresh_token")
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        raise ValueError("Google did not issue an offline credential. Try connecting again.")
    return access_token, refresh_token


async def account_email(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            GMAIL_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise ValueError("The connected Gmail account could not be identified.")
    email = response.json().get("emailAddress")
    if not isinstance(email, str) or not _ADDRESS.fullmatch(email.lower()):
        raise ValueError("Google returned an invalid Gmail account address.")
    return email.lower()
