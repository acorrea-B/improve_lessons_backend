"""User-local wall-clock helpers (plan.md § Mandatory Standards).

Every user-time-zone conversion used by the application lives here (the
only place together with ``app/core/strategies`` allowed to construct a
non-UTC ZoneInfo), so the static lint in ``tests/core/`` can prove no
module performs an implicit local-time conversion.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import normalize_to_utc


def wall_clock_in_zone(instant: datetime, time_zone: str) -> datetime:
    """The instant expressed as the user's local wall clock (aware)."""
    from app.core.time.utc import require_aware_utc

    return require_aware_utc(instant).astimezone(zone_for(time_zone))


def utc_from_wall_clock(
    day, hhmm: str, time_zone: str
) -> datetime:
    """Resolve a local ``HH:MM`` on calendar *day* to a UTC instant."""
    hour, minute = int(hhmm[:2]), int(hhmm[3:5])
    naive = datetime(day.year, day.month, day.day, hour, minute)
    return normalize_to_utc(naive.replace(tzinfo=zone_for(time_zone)))


def format_local(instant: datetime, time_zone: str, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    """Format an instant as the user's local wall clock (for emails)."""
    return wall_clock_in_zone(instant, time_zone).strftime(fmt)


def day_window(calendar_day: str, time_zone: str) -> tuple[datetime, datetime]:
    """[local 00:00, next-day local 00:00) of ``YYYY-MM-DD`` as UTC."""
    from datetime import date as date_type

    day = date_type.fromisoformat(calendar_day)
    zone = zone_for(time_zone)
    local_midnight = datetime(day.year, day.month, day.day, tzinfo=zone)
    return (
        normalize_to_utc(local_midnight),
        normalize_to_utc(local_midnight + timedelta(days=1)),
    )


def local_date_of(instant: datetime, time_zone: str) -> "date":
    return wall_clock_in_zone(instant, time_zone).date()