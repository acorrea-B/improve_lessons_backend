"""Week boundary strategy (FR-051).

Monday 00:00 → next Monday 00:00 in the *user's* time zone; the instants
returned are UTC (stored as UTC per the mandatory standard).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import normalize_to_utc, require_aware_utc


def week_start_for_wall_clock(instant: datetime, time_zone: str) -> datetime:
    """Return (as UTC) Monday 00:00 of the week containing *instant*."""
    aware = require_aware_utc(instant)
    local = aware.astimezone(zone_for(time_zone))
    monday = local.date() - timedelta(days=local.weekday())
    week_start_local = datetime(
        monday.year, monday.month, monday.day, tzinfo=zone_for(time_zone)
    )
    return normalize_to_utc(week_start_local)


def week_end_for_wall_clock(week_start_at: datetime, time_zone: str) -> datetime:
    """Next Monday 00:00 in the user's tz, as UTC."""
    aware = require_aware_utc(week_start_at)
    local = aware.astimezone(zone_for(time_zone))
    next_monday = local.date() + timedelta(days=7)
    week_end_local = datetime(
        next_monday.year, next_monday.month, next_monday.day, tzinfo=zone_for(time_zone)
    )
    return normalize_to_utc(week_end_local)


def resolve_day(calendar_day: str, time_zone: str) -> tuple[datetime, datetime]:
    """Resolve a ``YYYY-MM-DD`` local calendar date to its week window.

    The day must be a Monday in the user's time zone (US-8 contract);
    raises ``ValueError`` with a ``invalid_week_boundary`` message otherwise.
    """
    from datetime import date as date_type

    day = date_type.fromisoformat(calendar_day)
    if day.weekday() != 0:
        raise ValueError(
            "invalid_week_boundary: the date must be a Monday in the user's time zone."
        )
    local_midnight = datetime(day.year, day.month, day.day, tzinfo=zone_for(time_zone))
    start = normalize_to_utc(local_midnight)
    return start, week_end_for_wall_clock(start, time_zone)


class WeekBoundaryStrategy:
    """Computes the [week_start_at, week_end_at) window in the user's tz."""

    def resolve(self, instant: datetime, time_zone: str) -> tuple[datetime, datetime]:
        start = week_start_for_wall_clock(instant, time_zone)
        return start, week_end_for_wall_clock(start, time_zone)

    def resolve_local_day(self, calendar_day: str, time_zone: str) -> tuple[datetime, datetime]:
        return resolve_day(calendar_day, time_zone)