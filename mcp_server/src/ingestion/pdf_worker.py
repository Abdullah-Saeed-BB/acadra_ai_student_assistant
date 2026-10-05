"""Isolated PDF text extractor. Called only as a bounded subprocess."""

from io import BytesIO
import json
import sys

from pypdf import PdfReader

from src.ingestion.text import clean_manual_text

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PAGES = 20
MAX_TEXT_BYTES = 64 * 1024


def extract(data: bytes) -> dict[str, str]:
    if not data.startswith(b"%PDF-") or len(data) > MAX_FILE_BYTES:
        return {"error": "invalid_pdf"}
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            return {"error": "encrypted_pdf"}
        if len(reader.pages) > MAX_PAGES:
            return {"error": "too_many_pages"}
        parts: list[str] = []
        byte_count = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            byte_count += len(page_text.encode("utf-8"))
            if byte_count > MAX_TEXT_BYTES:
                return {"error": "text_too_large"}
            parts.append(page_text)
        clean_text = clean_manual_text("\n".join(parts))
        if not clean_text:
            return {"error": "no_extractable_text"}
        if len(clean_text.encode("utf-8")) > MAX_TEXT_BYTES:
            return {"error": "text_too_large"}
        return {"clean_text": clean_text}
    except Exception:
        return {"error": "invalid_pdf"}


def main() -> None:
    data = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
    result = extract(data)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
