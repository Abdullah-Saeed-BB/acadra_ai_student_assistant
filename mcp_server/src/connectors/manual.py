"""Acquire bounded, student-supplied plain text for the ingestion pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.ingestion.text import clean_manual_text

MAX_TEXT_BYTES = 64 * 1024
MAX_TITLE_LENGTH = 200


@dataclass(frozen=True)
class ManualTextEnvelope:
    source_document_id: UUID | None
    title: str | None
    raw_content: str
    clean_text: str
    observed_at: datetime


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

    if title is not None:
        title = title.strip()
        if not title:
            raise ValueError("Title must not be empty.")
        if len(title) > MAX_TITLE_LENGTH:
            raise ValueError("Title must be 200 characters or fewer.")
        if "\x00" in title:
            raise ValueError("Title must not contain NUL characters.")

    return ManualTextEnvelope(
        source_document_id=source_document_id,
        title=title,
        raw_content=text,
        clean_text=clean_text,
        observed_at=datetime.now(timezone.utc),
    )
