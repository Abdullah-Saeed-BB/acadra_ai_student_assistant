"""Structure-aware splitting of bounded source text for extraction.

A single extraction call over one long, heterogeneous document has three
failure modes: the model self-limits below the real item count, the completion
budget runs out, and one schema violation invalidates the whole document. This
module splits the clean text at structural boundaries (HTML block lines, email
paragraph lines, PDF lines) into overlapping windows that each fit one bounded
extraction call.

Splitting is deterministic and content-preserving. Windows overlap by a bounded
number of characters so an item that sits on a boundary is still seen in full by
at least one window; the merge stage removes the overlap duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_CHARS = 2200
DEFAULT_OVERLAP_CHARS = 350
MIN_MAX_CHARS = 200
MIN_SPLIT_CHARS = 250


@dataclass(frozen=True)
class TextChunk:
    """One extraction window plus its character span in the original text."""

    index: int
    text: str
    start: int
    end: int


def _block_spans(text: str, max_chars: int, overlap_chars: int) -> list[tuple[int, int]]:
    """Return the spans of non-empty structural blocks (lines).

    A source line that is longer than ``max_chars`` is hard-split into
    overlapping pieces so no single block can overflow one window.
    """
    spans: list[tuple[int, int]] = []
    position = 0
    for line in text.split("\n"):
        start = position
        end = position + len(line)
        position = end + 1  # the newline that followed this line
        if not line.strip():
            continue
        if len(line) <= max_chars:
            spans.append((start, end))
            continue
        step = max(1, max_chars - overlap_chars)
        piece = 0
        while piece < len(line):
            spans.append((start + piece, min(start + piece + max_chars, end)))
            piece += step
    return spans


def chunk_source_text(
    text: str, *, max_chars: int = DEFAULT_MAX_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS
) -> list[TextChunk]:
    """Split ``text`` into overlapping windows at structural boundaries.

    Returns an empty list only for blank text. A short text yields one chunk
    whose span covers the whole input.
    """
    max_chars = max(MIN_MAX_CHARS, int(max_chars))
    overlap_chars = max(0, min(int(overlap_chars), max_chars // 2))
    if not text or not text.strip():
        return []
    if len(text) <= max_chars:
        return [TextChunk(0, text, 0, len(text))]

    blocks = _block_spans(text, max_chars, overlap_chars)
    if not blocks:
        return [TextChunk(0, text, 0, len(text))]

    chunks: list[TextChunk] = []
    count = len(blocks)
    start = 0
    while start < count:
        chunk_start = blocks[start][0]
        end = blocks[start][1]
        cursor = start + 1
        while cursor < count and blocks[cursor][1] - chunk_start <= max_chars:
            end = blocks[cursor][1]
            cursor += 1
        chunks.append(TextChunk(len(chunks), text[chunk_start:end], chunk_start, end))
        if cursor >= count:
            break
        # Re-open the next window on the last block that starts at or before the
        # overlap boundary, so the tail of this window is seen again.
        target = end - overlap_chars
        follow = start + 1
        while follow < count and blocks[follow][0] <= target:
            follow += 1
        start = max(follow - 1, start + 1)
    return chunks


def split_for_retry(text: str, *, overlap_chars: int) -> list[str]:
    """Split a failed window into smaller overlapping windows.

    The target window size is half the failed window, so each piece is strictly
    smaller than what failed, guaranteeing progress. Structural boundaries are
    preserved.
    """
    target = max(MIN_SPLIT_CHARS, len(text) // 2)
    parts = chunk_source_text(
        text, max_chars=target, overlap_chars=min(overlap_chars, max(0, target // 4))
    )
    if len(parts) >= 2:
        return [part.text for part in parts]
    midpoint = len(text) // 2
    return [text[:midpoint], text[midpoint:]]
