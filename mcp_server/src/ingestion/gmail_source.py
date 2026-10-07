"""Strict Gmail intake: bounded message text and immutable provider identity."""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.utils import getaddresses
import re
from uuid import UUID

from src.ingestion.email_text import _decode_header
from src.ingestion.file_text import _VisibleHTML, _VOID_TAGS
from src.ingestion.text import clean_manual_text

MAX_TEXT_BYTES = 64 * 1024
MAX_PART_BYTES = 256 * 1024
MAX_PARTS = 100


class EmailIntakeError(ValueError):
    """A safe error code, with no source text in its message."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class GmailSourceEnvelope:
    connection_id: UUID
    external_id: str
    sender: str
    title: str
    original_ref: str
    source_updated_at: datetime
    observed_at: datetime
    clean_text: str
    source_type: str = "gmail"


def message_headers(payload: dict) -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise EmailIntakeError("invalid_message")
    message_id = payload.get("id")
    if not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id):
        raise EmailIntakeError("invalid_message_id")
    root = payload.get("payload")
    if not isinstance(root, dict) or not isinstance(root.get("headers", []), list):
        raise EmailIntakeError("invalid_headers")
    headers: dict[str, list[str]] = {}
    for header in root.get("headers", []):
        if not isinstance(header, dict) or not isinstance(header.get("value"), str):
            raise EmailIntakeError("invalid_headers")
        headers.setdefault(str(header.get("name", "")).lower(), []).append(header["value"])
    senders = headers.get("from", [])
    if len(senders) != 1 or len(senders[0]) > 4096:
        raise EmailIntakeError("invalid_sender")
    try:
        addresses = getaddresses([_decode_header(senders[0])])
    except ValueError:
        raise EmailIntakeError("invalid_sender") from None
    if len(addresses) != 1 or not addresses[0][1] or "@" not in addresses[0][1]:
        raise EmailIntakeError("invalid_sender")
    subjects = headers.get("subject", [""])
    if len(subjects) != 1 or len(subjects[0]) > 8192:
        raise EmailIntakeError("invalid_subject")
    subject = clean_manual_text(_decode_header(subjects[0]))
    if "\x00" in subject:
        raise EmailIntakeError("invalid_subject")
    return message_id, addresses[0][1].lower(), subject


class _EmailHTML(_VisibleHTML):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        quote_class = any(
            name == "class" and set((value or "").split()) & {"gmail_quote", "yahoo_quoted", "moz-cite-prefix"}
            for name, value in attrs
        )
        if not self.skip_tag and (tag == "blockquote" or quote_class):
            if tag not in _VOID_TAGS:
                self.skip_tag, self.skip_depth = tag, 1
            return
        super().handle_starttag(tag, attrs)


def _unquote(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.match(r"^\s*On .{1,500}wrote:\s*$", line, flags=re.I):
            break
        if re.match(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", line, flags=re.I):
            break
        if not line.lstrip().startswith(">"):
            lines.append(line)
    return clean_manual_text("\n".join(lines))


def _body(part: dict, budget: list[int], depth: int = 0) -> tuple[str, bool, bool]:
    """Return text, whether a supported body exists, and plain-text preference."""
    budget[0] += 1
    if budget[0] > MAX_PARTS or depth > 20 or not isinstance(part, dict):
        raise EmailIntakeError("invalid_mime_structure")
    headers = part.get("headers") or []
    if not isinstance(headers, list) or any(not isinstance(h, dict) for h in headers):
        raise EmailIntakeError("invalid_mime_structure")
    if part.get("filename") or any(
        str(h.get("name", "")).lower() == "content-disposition"
        and str(h.get("value", "")).lower().startswith("attachment") for h in headers
    ):
        return "", False, False
    mime = str(part.get("mimeType", "")).lower()
    if mime.startswith("multipart/"):
        children = part.get("parts") or []
        if not isinstance(children, list) or len(children) > MAX_PARTS:
            raise EmailIntakeError("invalid_mime_structure")
        bodies = [_body(child, budget, depth + 1) for child in children]
        supported = [body for body in bodies if body[1]]
        if mime == "multipart/alternative" and supported:
            return next((body for body in supported if body[2]), supported[0])
        return "\n\n".join(body[0] for body in supported), bool(supported), all(body[2] for body in supported)
    if mime not in {"text/plain", "text/html"}:
        return "", False, False
    body = part.get("body") or {}
    if not isinstance(body, dict) or body.get("attachmentId"):
        raise EmailIntakeError("external_body_unsupported")
    encoded = body.get("data", "")
    if not isinstance(encoded, str):
        raise EmailIntakeError("invalid_body_encoding")
    if len(encoded) > 4 * ((MAX_PART_BYTES + 2) // 3):
        raise EmailIntakeError("email_too_large")
    try:
        data = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        raise EmailIntakeError("invalid_body_encoding") from None
    if len(data) > MAX_PART_BYTES:
        raise EmailIntakeError("email_too_large")
    content_type = Message()
    content_type["Content-Type"] = str(next(
        (h.get("value") for h in headers if str(h.get("name", "")).lower() == "content-type"), mime,
    ))
    try:
        decoded = data.decode(content_type.get_content_charset() or "utf-8")
    except (LookupError, UnicodeError):
        raise EmailIntakeError("invalid_body_encoding") from None
    if "\x00" in decoded:
        raise EmailIntakeError("invalid_body_encoding")
    if mime == "text/html":
        parser = _EmailHTML()
        parser.feed(decoded)
        parser.close()
        decoded = "".join(parser.parts)
    return _unquote(decoded), True, mime == "text/plain"


def prepare_gmail_source(
    connection_id: UUID, payload: dict, *, observed_at: datetime | None = None,
) -> GmailSourceEnvelope:
    message_id, sender, subject = message_headers(payload)
    try:
        received_at = datetime.fromtimestamp(int(payload["internalDate"]) / 1000, tz=timezone.utc)
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        raise EmailIntakeError("invalid_provider_timestamp") from None
    body, supported, _ = _body(payload["payload"], [0])
    if not supported:
        raise EmailIntakeError("unsupported_email_body")
    clean_text = clean_manual_text(f"Subject: {subject}\n\n{body}" if subject else body)
    if not clean_text:
        raise EmailIntakeError("empty_email")
    if len(clean_text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise EmailIntakeError("email_too_large")
    return GmailSourceEnvelope(
        connection_id=connection_id, external_id=message_id, sender=sender,
        title=subject[:200] or "Email message", original_ref=f"gmail:message/{message_id}",
        source_updated_at=received_at, observed_at=observed_at or datetime.now(timezone.utc),
        clean_text=clean_text,
    )
