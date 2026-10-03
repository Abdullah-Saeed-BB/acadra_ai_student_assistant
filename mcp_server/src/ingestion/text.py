"""Plain-text normalization shared by future source adapters."""

import unicodedata


def clean_manual_text(raw: str) -> str:
    """Normalize Unicode and line endings without interpreting source content."""
    normalized = unicodedata.normalize("NFC", raw)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()
