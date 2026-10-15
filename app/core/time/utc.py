"""Central date/time helpers — the ONLY place in ``app/`` allowed to handle
time-zone conversion logic (plan.md § Mandatory Standards § Date and Time
Handling).

Rules enforced here:

- All internal calculations use timezone-aware UTC ``datetime`` objects.
- Naive datetimes are rejected everywhere by ``require_aware_utc``.
- ``parse_iso_to_utc`` rejects naive ISO strings with a ``ValueError`` whose
  message starts with ``invalid_timestamp``.
- ``datetime.now()`` without a ``tz`` argument is forbidden elsewhere in
  ``app/``; the only allowed call is ``now_utc()`` below.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

__all__ = [
    "UTC",
    "now_utc",
    "parse_iso_to_utc",
    "to_utc_instant",
    "require_aware_utc",
    "AwareDatetime",
]


def now_utc() -> datetime:
    """Return the current instant as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def require_aware_utc(value: datetime, *, argument: str = "value") -> datetime:
    """Raise ``ValueError`` when *value* is a naive datetime.

    Aware datetimes are returned normalized to UTC. This is the guard used
    at every adapter and module boundary.
    """
    if not isinstance(value, datetime):
        raise ValueError(f"{argument}_not_a_datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{argument}_naive_datetime_not_allowed")
    return normalize_to_utc(value)


def to_utc_instant(value: datetime) -> datetime:
    """Convert an aware datetime to the equivalent UTC instant."""
    return require_aware_utc(value)


def normalize_to_utc(value: datetime) -> datetime:
    """Return *value* converted to UTC (aware datetimes only)."""
    return value.astimezone(UTC)


def parse_iso_to_utc(value: str, *, argument: str = "timestamp") -> datetime:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime.

    Naive strings (no offset) and empty values raise ``ValueError`` with a
    message that starts with ``invalid_timestamp`` so the API layer can map
    it to ``400 Bad Request`` / ``error.code = "invalid_timestamp"``.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid_timestamp: empty {argument}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid_timestamp: {exc}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(
            f"invalid_timestamp: naive timestamps are not allowed, "
            f"include an explicit UTC offset (got: {value})"
        )
    return normalize_to_utc(parsed)


def _validate_utc_instant(value):
    """Pydantic ``BeforeValidator``: reject naive, normalize offsets to UTC.

    Also accepts ISO 8601 strings (request payloads arrive as strings) with
    the same rules: explicit offset required, normalized to UTC.
    """
    if isinstance(value, str):
        return parse_iso_to_utc(value)
    if not isinstance(value, datetime):
        raise ValueError("invalid_timestamp: expected a datetime or ISO string")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "invalid_timestamp: naive timestamps are not allowed, "
            "include an explicit UTC offset"
        )
    return normalize_to_utc(value)


def _serialize_z_suffix(value: datetime) -> str:
    """Pydantic serializer: always emit ISO 8601 with the ``Z`` suffix.

    Explicit offsets such as ``+00:00`` are never emitted (contract §
    Conventions).
    """
    return normalize_to_utc(value).isoformat().replace("+00:00", "Z")


# The single Pydantic annotation bound to UTC. Every API request/response
# model that carries an instant uses this type, so validation and the
# Z-suffix serialization are configured in one place.
# ``when_used="json"``: Python-mode dumps (persistence!) keep real datetime
# objects — only JSON serialization emits the Z-suffixed string.
AwareDatetime = Annotated[
    datetime,
    BeforeValidator(_validate_utc_instant),
    PlainSerializer(_serialize_z_suffix, return_type=str, when_used="json"),
]


def minutes_after(instant: datetime, minutes: int) -> datetime:
    """Return *instant* plus the given number of minutes (UTC arithmetic)."""
    return require_aware_utc(instant) + timedelta(minutes=minutes)