"""Shared endpoint helpers: user-tz date ranges and feature gating."""

from __future__ import annotations

from datetime import timedelta

from app.core.errors import ValidationErrorDetail
from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import normalize_to_utc

#: Default listing window when no date range is given.
DEFAULT_RANGE_DAYS = 90


def parse_date_range(
    from_date: str | None, to_date: str | None, time_zone: str
) -> tuple:
    """Contract § Sessions: date ranges are interpreted in the user's tz.

    The window is [from 00:00 local, to+1day 00:00 local) expressed as UTC
    instants. ``to`` is inclusive as a calendar date. Without both ends the
    default window is the trailing 90 days in the user's tz.
    """
    if not from_date and not to_date:
        return _default_window(time_zone)
    if from_date:
        start_local = _day_start(from_date, time_zone)
    else:
        start_local = _day_start(to_date, time_zone)
    if to_date:
        end_local = _day_start(to_date, time_zone) + timedelta(days=1)
    else:
        end_local = _day_start(from_date, time_zone) + timedelta(days=DEFAULT_RANGE_DAYS)
    return normalize_to_utc(start_local), normalize_to_utc(end_local)


def _default_window(time_zone: str) -> tuple:
    from app.core.time.utc import now_utc
    from app.core.time.wall_clock import wall_clock_in_zone

    today_local = wall_clock_in_zone(now_utc(), time_zone)
    start_local = today_local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=DEFAULT_RANGE_DAYS
    )
    end_local = today_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return normalize_to_utc(start_local), normalize_to_utc(end_local)


def _day_start(value: str, time_zone: str) -> "datetime":
    from datetime import date as date_type
    from datetime import datetime as datetime_type

    try:
        day = date_type.fromisoformat(value)
    except ValueError as exc:
        raise ValidationErrorDetail(
            code="invalid_date",
            message="Dates must be YYYY-MM-DD calendar dates (local, NOT instants).",
            details={"field": "from/to", "value": value},
        ) from exc
    return datetime_type(day.year, day.month, day.day, tzinfo=zone_for(time_zone))