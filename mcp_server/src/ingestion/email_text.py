"""Turn a Gmail FULL payload into bounded text for console inspection."""

import base64
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr

from src.ingestion.file_text import extract_html_text
from src.ingestion.text import clean_manual_text

MAX_PART_BYTES = 256 * 1024
MAX_PRINT_BYTES = 64 * 1024
MAX_PARTS = 30


@dataclass(frozen=True)
class EmailPreview:
    id: str
    sender: str
    subject: str
    content: str


def _decode_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeError, LookupError):
        return value


def _part_text(part: dict) -> tuple[str, str] | None:
    if part.get("filename"):
        return None
    mime = str(part.get("mimeType", "")).lower()
    if mime not in {"text/plain", "text/html"}:
        return None
    encoded = (part.get("body") or {}).get("data")
    if not isinstance(encoded, str):
        return None
    if len(encoded) > MAX_PART_BYTES * 2:
        return None
    try:
        data = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, base64.binascii.Error):
        return None
    if len(data) > MAX_PART_BYTES:
        return None
    content_type = Message()
    content_type["Content-Type"] = str(next(
        (header.get("value") for header in (part.get("headers") or [])
         if str(header.get("name", "")).lower() == "content-type"),
        mime,
    ))
    charset = content_type.get_content_charset() or "utf-8"
    try:
        text = data.decode(charset, errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")
    return mime, text


def _bounded(text: str) -> str:
    encoded = clean_manual_text(text).encode("utf-8")
    if len(encoded) <= MAX_PRINT_BYTES:
        return encoded.decode("utf-8")
    return encoded[:MAX_PRINT_BYTES].decode("utf-8", errors="ignore") + "\n[content truncated]"


def preview_message(payload: dict) -> EmailPreview:
    """Prefer plain text, then sanitized HTML; never decode attachment parts."""
    message_id = payload.get("id")
    if not isinstance(message_id, str) or not message_id:
        raise ValueError("Gmail message is missing an ID.")
    root = payload.get("payload") or {}
    headers = {
        str(header.get("name", "")).lower(): str(header.get("value", ""))
        for header in (root.get("headers") or []) if isinstance(header, dict)
    }
    sender = parseaddr(_decode_header(headers.get("from", "")))[1].lower()
    subject = _bounded(_decode_header(headers.get("subject", "(no subject)")))[:200]
    plain: list[str] = []
    html: list[str] = []
    stack = [root]
    visited = 0
    while stack and visited < MAX_PARTS:
        part = stack.pop()
        if not isinstance(part, dict):
            continue
        visited += 1
        found = _part_text(part)
        if found:
            (plain if found[0] == "text/plain" else html).append(found[1])
        children = part.get("parts") or []
        if isinstance(children, list):
            stack.extend(reversed(children[:MAX_PARTS]))
    if plain:
        content = _bounded("\n".join(plain))
    elif html:
        markup = "\n".join(html).encode("utf-8")[:MAX_PART_BYTES]
        try:
            content = _bounded(extract_html_text(markup))
        except ValueError:
            content = "[HTML content could not be displayed]"
    else:
        content = "[no supported text body]"
    return EmailPreview(message_id, sender, subject, content)
