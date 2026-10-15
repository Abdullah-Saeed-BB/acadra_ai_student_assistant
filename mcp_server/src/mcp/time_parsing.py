"""Lenient parsing for MCP tool date-time filter bounds.

LLMs routinely answer range-filter prompts with date-only strings such as
``2026-10-15`` even when the published tool schema expects a date-time.
Strict schema validation rejects those calls before the tool runs, and the
model cannot recover from the opaque failure, so MCP date bounds accept
either a full ISO-8601 date-time or a date-only day and normalize to an
aware datetime.

The REST query contract in ``api/schemas.py`` stays strict: it serves the
web client, which always sends full ISO-8601 date-times with a UTC offset.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BeforeValidator

_FORMAT_HINT = (
    "Use an ISO 8601 date-time with a UTC offset (e.g. 2026-10-15T09:00:00Z) "
    "or a date-only YYYY-MM-DD value."
)


def parse_datetime_bound(value: str | datetime, *, param_name: str) -> datetime:
    """Normalize a filter bound into a timezone-aware datetime.

    Accepts a full ISO-8601 date-time or a date-only ``YYYY-MM-DD`` value
    (interpreted as midnight UTC). A date-time without a UTC offset is
    assumed to be UTC. Raises ``ValueError`` with a correction hint for
    anything else, which the tool error envelope maps to ``invalid_input``.
    """
    parsed = value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            raise ValueError(f"{param_name} is not a valid ISO 8601 date or date-time. {_FORMAT_HINT}") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_to_aware(value: Any) -> Any:
    if value is None or isinstance(value, datetime) and value.tzinfo is not None:
        return value
    return parse_datetime_bound(value, param_name="value")


#: Aware ``datetime`` that also accepts date-only and naive ISO-8601 strings.
#: Used by the Pydantic input-contract models in ``schemas.py`` so they accept
#: the same values the MCP tool signatures accept.
LenientAwareDatetime = Annotated[datetime, BeforeValidator(_coerce_to_aware)]
