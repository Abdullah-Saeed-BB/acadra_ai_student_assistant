"""Bounded HTML/PDF text extraction for manually uploaded files."""

from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from src.ingestion.text import clean_manual_text

MAX_HTML_BYTES = 256 * 1024
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_CLEAN_TEXT_BYTES = 64 * 1024
PDF_TIMEOUT_SECONDS = 20

_IGNORED_TAGS = {"script", "style", "template", "head", "svg", "iframe", "object", "nav", "footer"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_BLOCK_TAGS = {
    "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "h1", "h2",
    "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "ol", "p", "pre",
    "section", "table", "td", "th", "tr", "ul",
}


class _VisibleHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_tag: str | None = None
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth += 1
            return
        hidden = any(
            name == "hidden"
            or (name == "aria-hidden" and (value or "").lower() == "true")
            or (name == "style" and re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", value or "", re.I))
            for name, value in attrs
        )
        if tag in _IGNORED_TAGS or hidden:
            if tag not in _VOID_TAGS:
                self.skip_tag = tag
                self.skip_depth = 1
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_tag:
            if tag == self.skip_tag:
                self.skip_depth -= 1
                if self.skip_depth == 0:
                    self.skip_tag = None
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_tag:
            # Adjacent inline elements may split one word. Keep their exact
            # boundary while turning source formatting whitespace into spaces.
            self.parts.append(re.sub(r"\s+", " ", data))


def _bound_clean_text(text: str) -> str:
    cleaned = clean_manual_text(text)
    if not cleaned:
        raise ValueError("File has no extractable text.")
    if "\x00" in cleaned:
        raise ValueError("Extracted text contains NUL characters.")
    if len(cleaned.encode("utf-8")) > MAX_CLEAN_TEXT_BYTES:
        raise ValueError("Extracted text must be 64 KiB or smaller.")
    return cleaned


def extract_html_text(data: bytes) -> str:
    if not data or len(data) > MAX_HTML_BYTES:
        raise ValueError("HTML file must be nonempty and 256 KiB or smaller.")
    try:
        markup = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("HTML file must use UTF-8 encoding.") from None
    parser = _VisibleHTML()
    parser.feed(markup)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n(?:[ \t]*\n)+", "\n", text)
    return _bound_clean_text(text)


async def extract_pdf_text(data: bytes) -> str:
    if not data or len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF file must be nonempty and 5 MiB or smaller.")
    if not data.startswith(b"%PDF-"):
        raise ValueError("File is not a valid PDF.")
    backend_root = Path(__file__).resolve().parents[2]
    allowed_env = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH", "VIRTUAL_ENV"}
    worker_env = {key: value for key, value in os.environ.items() if key.upper() in allowed_env}
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    worker = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "src.ingestion.pdf_worker",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, cwd=str(backend_root), env=worker_env,
        creationflags=creationflags,
    )
    try:
        output, _ = await asyncio.wait_for(worker.communicate(data), PDF_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        worker.kill()
        await worker.communicate()
        raise ValueError("PDF text extraction timed out.") from None
    if worker.returncode != 0 or len(output) > 4 * MAX_CLEAN_TEXT_BYTES:
        raise ValueError("PDF text could not be extracted.")
    try:
        result = json.loads(output)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("PDF text could not be extracted.") from None
    errors = {
        "invalid_pdf": "File is not a valid PDF.",
        "encrypted_pdf": "Password-protected PDFs are not supported.",
        "too_many_pages": "PDF must have 20 pages or fewer.",
        "no_extractable_text": "PDF has no extractable text; scanned PDFs need OCR.",
        "text_too_large": "Extracted text must be 64 KiB or smaller.",
    }
    if "error" in result:
        raise ValueError(errors.get(result["error"], "PDF text could not be extracted."))
    if not isinstance(result.get("clean_text"), str):
        raise ValueError("PDF text could not be extracted.")
    return _bound_clean_text(result["clean_text"])
