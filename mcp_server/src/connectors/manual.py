"""Acquire bounded, student-supplied text and files for the ingestion pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import UUID

from src.ingestion.file_text import MAX_HTML_BYTES, MAX_PDF_BYTES, extract_html_text, extract_pdf_text
from src.ingestion.text import clean_manual_text

MAX_TEXT_BYTES = 64 * 1024
MAX_TITLE_LENGTH = 200


@dataclass(frozen=True)
class ManualTextEnvelope:
    source_document_id: UUID | None
    title: str | None
    raw_content: str | None
    clean_text: str
    observed_at: datetime
    source_type: str = "text"
    original_ref: str | None = None
    file_bytes: bytes | None = None
    media_type: str | None = None


class UnsupportedManualFileType(ValueError):
    """The uploaded extension or declared media type is unsupported."""


class ManualFileTooLarge(ValueError):
    """The file exceeds its format-specific upload limit."""


def _validate_title(title: str | None) -> str | None:
    if title is None:
        return None
    title = title.strip()
    if not title:
        raise ValueError("Title must not be empty.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError("Title must be 200 characters or fewer.")
    if "\x00" in title:
        raise ValueError("Title must not contain NUL characters.")
    return title


def prepare_manual_text(
    text: str, *, title: str | None = None, source_document_id: UUID | None = None
) -> ManualTextEnvelope:
    """A missing ID creates a new source; an ID explicitly replaces one."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must not be empty.")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Text must be 64 KiB or smaller.")
    if "\x00" in text:
        raise ValueError("Text must not contain NUL characters.")

    clean_text = clean_manual_text(text)
    if not clean_text:
        raise ValueError("Text must contain readable content.")

    return ManualTextEnvelope(
        source_document_id=source_document_id,
        title=_validate_title(title),
        raw_content=text,
        clean_text=clean_text,
        observed_at=datetime.now(timezone.utc),
    )


async def prepare_manual_file(
    data: bytes, *, filename: str, content_type: str | None,
    title: str | None = None, source_document_id: UUID | None = None,
) -> ManualTextEnvelope:
    """Parse an uploaded HTML/PDF file without treating it as instructions."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("File must not be empty.")
    safe_name = re.split(r"[/\\]", filename or "")[-1]
    if not safe_name or len(safe_name) > 200 or "\x00" in safe_name:
        raise ValueError("File must have a valid name of 200 characters or fewer.")
    validated_title = _validate_title(title)
    suffix = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if suffix in {"html", "htm"}:
        if declared not in {"text/html", "application/xhtml+xml", "application/octet-stream", ""}:
            raise UnsupportedManualFileType("HTML file media type is unsupported.")
        if len(data) > MAX_HTML_BYTES:
            raise ManualFileTooLarge("HTML file must be 256 KiB or smaller.")
        source_type, media_type = "html", "text/html"
        clean_text = extract_html_text(data)
    elif suffix == "pdf":
        if declared not in {"application/pdf", "application/octet-stream", ""}:
            raise UnsupportedManualFileType("PDF file media type is unsupported.")
        if len(data) > MAX_PDF_BYTES:
            raise ManualFileTooLarge("PDF file must be 5 MiB or smaller.")
        source_type, media_type = "pdf", "application/pdf"
        clean_text = await extract_pdf_text(data)
    else:
        raise UnsupportedManualFileType("Only .html, .htm, and .pdf files are supported.")
    return ManualTextEnvelope(
        source_document_id=source_document_id,
        title=validated_title or safe_name,
        raw_content=None,
        clean_text=clean_text,
        observed_at=datetime.now(timezone.utc),
        source_type=source_type,
        original_ref=safe_name,
        file_bytes=data,
        media_type=media_type,
    )
