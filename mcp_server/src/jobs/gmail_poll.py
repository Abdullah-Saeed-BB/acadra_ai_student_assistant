"""Check Gmail once a minute and print new allowed-sender messages."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable

from dotenv import load_dotenv

from src.auth.credential_store import load_gmail_refresh_token
from src.connectors.gmail import GmailClient, GmailRequestError
from src.ingestion.email_text import preview_message
from src.services.gmail_connection import get_gmail_connection
from src.services.gmail_poll_state import read_history_id, save_history_id

POLL_SECONDS = 60
MAX_HISTORY_PAGES = 20
MAX_MESSAGES_PER_POLL = 500


class GmailCursorExpired(RuntimeError):
    """History cannot be resumed without a deliberate full rescan."""


async def poll_once(
    connection, client,
    *, read_cursor=read_history_id, write_cursor=save_history_id,
    emit: Callable[[str], None] = print,
) -> int:
    """Print new messages, then persist the cursor after the complete poll."""
    cursor = await read_cursor(connection.id)
    if cursor is None:
        baseline = await client.profile_history_id()
        await write_cursor(connection.id, baseline)
        emit("[gmail] Initialized at the current mailbox position; watching for new messages.")
        return 0

    message_ids: list[str] = []
    seen: set[str] = set()
    page_token = None
    latest_history_id = cursor
    for _ in range(MAX_HISTORY_PAGES):
        try:
            page = await client.history_page(cursor, page_token)
        except GmailRequestError as exc:
            if exc.status_code == 404:
                raise GmailCursorExpired(
                    "Gmail history expired; a full rescan is needed before polling can resume."
                ) from None
            raise
        records = page.get("history") or []
        if not isinstance(records, list):
            raise RuntimeError("Google returned invalid Gmail history.")
        for record in records:
            for added in record.get("messagesAdded", []):
                message_id = added.get("message", {}).get("id")
                if isinstance(message_id, str) and message_id not in seen:
                    seen.add(message_id)
                    message_ids.append(message_id)
                    if len(message_ids) > MAX_MESSAGES_PER_POLL:
                        raise RuntimeError("Too many new Gmail messages in one poll.")
        latest_history_id = page.get("historyId", latest_history_id)
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    else:
        raise RuntimeError("Gmail history exceeded the per-poll page limit.")
    if not isinstance(latest_history_id, str) or not latest_history_id.isdecimal():
        raise RuntimeError("Google returned an invalid Gmail history ID.")

    allowed = set(connection.allowed_senders)
    printed = 0
    for message_id in message_ids:
        payload = await client.message(message_id)
        if payload is None:
            continue
        preview = preview_message(payload)
        if preview.sender not in allowed:
            continue
        emit(json.dumps({
            "id": preview.id,
            "sender": preview.sender,
            "subject": preview.subject,
            "content": preview.content,
        }, ensure_ascii=False))
        printed += 1
    await write_cursor(connection.id, latest_history_id)
    return printed


async def run_worker(*, once: bool = False) -> None:
    """Keep one authenticated Gmail client alive across minute-spaced polls."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    client: GmailClient | None = None
    credential_ref = None
    try:
        while True:
            started = time.monotonic()
            try:
                connection = await get_gmail_connection()
                if connection is None or connection.status != "connected" or not connection.credential_ref:
                    print("[gmail] Waiting for a connected Gmail account.", flush=True)
                elif not connection.allowed_senders:
                    print("[gmail] Waiting for allowed sender addresses.", flush=True)
                else:
                    if credential_ref != connection.credential_ref or client is None:
                        if client is not None:
                            await client.aclose()
                        client = None
                        refresh_token = await load_gmail_refresh_token(connection.credential_ref)
                        client_id = os.getenv("ACADRA_GMAIL_CLIENT_ID", "")
                        client_secret = os.getenv("ACADRA_GMAIL_CLIENT_SECRET", "")
                        if client_id in {"", "your_client_id"} or client_secret in {"", "your_client_secret"}:
                            raise RuntimeError("Gmail OAuth client settings are missing.")
                        client = GmailClient(refresh_token, client_id, client_secret)
                        credential_ref = connection.credential_ref
                    count = await poll_once(connection, client)
                    print(f"[gmail] Poll complete: {count} matching new message(s).", flush=True)
            except GmailCursorExpired as exc:
                print(f"[gmail] {exc}", file=sys.stderr, flush=True)
                raise SystemExit(2) from None
            except GmailRequestError as exc:
                print(f"[gmail] Provider error: HTTP {exc.status_code}; retrying next minute.", file=sys.stderr, flush=True)
                if once:
                    raise SystemExit(1) from None
            except Exception as exc:
                print(f"[gmail] Poll failed ({type(exc).__name__}); retrying next minute.", file=sys.stderr, flush=True)
                if once:
                    raise SystemExit(1) from None
            if once:
                return
            await asyncio.sleep(max(0, POLL_SECONDS - (time.monotonic() - started)))
    finally:
        if client is not None:
            await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Print new Gmail messages from allowed senders every minute.")
    parser.add_argument("--once", action="store_true", help="Run one poll and exit.")
    args = parser.parse_args()
    try:
        asyncio.run(run_worker(once=args.once))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
