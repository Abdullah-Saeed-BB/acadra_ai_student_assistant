"""Gmail OAuth, sender scope, and read-only mailbox requests."""

import re
import time
from urllib.parse import urlencode

import httpx

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_HISTORY_URL = "https://gmail.googleapis.com/gmail/v1/users/me/history"
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


class GmailRequestError(RuntimeError):
    """A Gmail request failed; only its HTTP status is safe to expose."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Gmail request failed with HTTP {status_code}.")


class GmailClient:
    """Small async Gmail client using an already connected account's refresh token."""

    def __init__(self, refresh_token: str, client_id: str, client_secret: str):
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = httpx.AsyncClient(timeout=20)
        self._access_token: str | None = None
        self._expires_at = 0.0

    async def __aenter__(self) -> "GmailClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._http.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _refresh(self) -> None:
        response = await self._http.post(GOOGLE_TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        })
        if response.status_code != 200:
            raise GmailRequestError(response.status_code)
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Google returned no Gmail access token.")
        self._access_token = token
        self._expires_at = time.monotonic() + max(0, int(payload.get("expires_in", 3600)) - 60)

    async def _get(self, url: str, *, params: dict | None = None) -> dict:
        if self._access_token is None or time.monotonic() >= self._expires_at:
            await self._refresh()
        response = await self._http.get(
            url, params=params, headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code == 401:
            await self._refresh()
            response = await self._http.get(
                url, params=params, headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code != 200:
            raise GmailRequestError(response.status_code)
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Google returned an invalid Gmail response.")
        return payload

    async def profile_history_id(self) -> str:
        payload = await self._get(GMAIL_PROFILE_URL)
        history_id = payload.get("historyId")
        if not isinstance(history_id, str) or not history_id:
            raise RuntimeError("Google returned no Gmail history ID.")
        return history_id

    async def history_page(self, start_history_id: str, page_token: str | None = None) -> dict:
        params = {"startHistoryId": start_history_id, "historyTypes": "messageAdded", "maxResults": 100}
        if page_token:
            params["pageToken"] = page_token
        return await self._get(GMAIL_HISTORY_URL, params=params)

    async def message(self, message_id: str) -> dict | None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id):
            raise ValueError("Gmail returned an invalid message ID.")
        try:
            return await self._get(f"{GMAIL_MESSAGES_URL}/{message_id}", params={"format": "full"})
        except GmailRequestError as exc:
            if exc.status_code == 404:
                return None  # The message disappeared after its history event.
            raise
