"""Month boundary strategy (FR-051): calendar month in the user's time zone."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import normalize_to_utc, require_aware_utc


def month_start_for_wall_clock(instant: datetime, time_zone: str) -> datetime:
    aware = require_aware_utc(instant)
    local = aware.astimezone(zone_for(time_zone))
    local_midnight = datetime(local.year, local.month, 1, tzinfo=zone_for(time_zone))
    return normalize_to_utc(local_midnight)


def month_end_for_wall_clock(month_start_at: datetime, time_zone: str) -> datetime:
    aware = require_aware_utc(month_start_at)
    local = aware.astimezone(zone_for(time_zone))
    year, month = local.year, local.month
    if month == 12:
        year, month = year + 1, 1
    else:
        month = month + 1
    local_midnight = datetime(year, month, 1, tzinfo=zone_for(time_zone))
    return normalize_to_utc(local_midnight)


def resolve_month(calendar_month: str, time_zone: str) -> tuple[datetime, datetime]:
    """Resolve ``YYYY-MM`` to [month_start, month_end) as UTC instants."""
    year_text, month_text = calendar_month.split("-")
    year, month = int(year_text), int(month_text)
    if not 1 <= month <= 12:
        raise ValueError("invalid_month_boundary: month must be in 1..12.")
    local_midnight = datetime(year, month, 1, tzinfo=zone_for(time_zone))
    start = normalize_to_utc(local_midnight)
    end_local_month = datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=zone_for(time_zone)) + timedelta(days=1)
    # Normalize day overflow (last day + 1 day == 1st of next month).
    end_local_midnight = end_local_month.replace(hour=0, minute=0)
    return start, normalize_to_utc(end_local_midnight)