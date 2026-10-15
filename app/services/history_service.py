"""History service (T081, US-8).

Composes the summary, daily-material, weekly and monthly services to
produce the per-day / per-week / per-month history views. Period
boundaries come from the user's time zone; late submissions remain
visible with their ``late`` status (constitution principle IV).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfo as _ZI  # noqa: F401

from app.core.errors import NotFoundError, ValidationErrorDetail
from app.core.ports.user_repository import UserRepository
from app.core.time.utc import normalize_to_utc

__all__ = ["HistoryService"]


def day_window(calendar_day: str, time_zone: str) -> tuple[datetime, datetime]:
    from datetime import date as date_type

    day = date_type.fromisoformat(calendar_day)
    zone = _ZI(time_zone)
    local_midnight = datetime(day.year, day.month, day.day, tzinfo=zone)
    return normalize_to_utc(local_midnight), normalize_to_utc(local_midnight + timedelta(days=1))


class HistoryService:
    def __init__(
        self,
        users: UserRepository,
        summaries,
        daily_materials,
        sessions,
        weekly_rollup,
        monthly_rollup,
    ) -> None:
        self._users = users
        self._summaries = summaries
        self._materials = daily_materials
        self._sessions = sessions
        self._weekly = weekly_rollup
        self._monthly = monthly_rollup

    async def day(self, owner_user_id: str, calendar_day: str) -> dict:
        start, end = day_window(calendar_day, await self._tz(owner_user_id))
        summaries = await self._summaries.list_in_range(owner_user_id, start, end)
        materials = await self._materials.list_in_range(owner_user_id, start, end)
        sessions = await self._sessions.list_for_owner(owner_user_id, from_instant=start, to_instant=end)
        if not summaries and not sessions:
            return {"date": calendar_day, "summaries": [], "materials": [], "sessions": [], "message": "No records for this day."}
        return {
            "date": calendar_day,
            "summaries": summaries,
            "materials": materials,
            "sessions": sessions,
        }

    async def week(self, owner_user_id: str, calendar_day: str) -> dict:
        from app.core.strategies.week_boundary_strategy import resolve_day

        if calendar_day:
            from datetime import date as date_type

            weekday = date_type.fromisoformat(calendar_day).weekday()
            if weekday != 0:
                raise ValidationErrorDetail(
                    code="invalid_week_boundary",
                    message="The date must be a Monday in the user's time zone.",
                    details={"field": "date"},
                )
        from app.core.strategies.week_boundary_strategy import resolve_day

        start, end = resolve_day(calendar_day, await self._tz(owner_user_id))
        weekly = await self._weekly.list_in_range(owner_user_id, from_instant=start, to_instant=end)
        day_view = await self.day(owner_user_id, calendar_day)
        return {"start_day": calendar_day, **day_view, "weekly_summaries": weekly}

    async def month(self, owner_user_id: str, calendar_month: str) -> dict:
        from app.core.strategies.month_boundary_strategy import resolve_month

        start, end = resolve_month(calendar_month, await self._tz(owner_user_id))
        summaries = await self._summaries.list_in_range(owner_user_id, start, end)
        weekly = await self._weekly.list_in_range(owner_user_id, from_instant=start, to_instant=end)
        monthly_summaries = await self._monthly.list_in_range(owner_user_id, from_instant=start, to_instant=end)
        materials = await self._materials.list_in_range(owner_user_id, start, end)
        return {
            "month": calendar_month,
            "summaries": summaries,
            "daily_materials": materials,
            "weekly_summaries": weekly,
            "monthly_summaries": monthly_summaries,
            "message": "No records for this month."
            if not summaries and not weekly
            else None,
        }

    async def range(self, owner_user_id: str, from_instant: datetime, to_instant: datetime) -> dict:
        from app.core.time.utc import require_aware_utc

        start = require_aware_utc(from_instant)
        end = require_aware_utc(to_instant)
        summaries = await self._summaries.list_in_range(owner_user_id, start, end)
        materials = await self._materials.list_in_range(owner_user_id, start, end)
        weekly = await self._weekly.list_in_range(owner_user_id, from_instant=start, to_instant=end)
        monthly = await self._monthly.list_in_range(owner_user_id, from_instant=start, to_instant=end)
        return {
            "summaries": summaries,
            "daily_materials": materials,
            "weekly_summaries": weekly,
            "monthly_summaries": monthly,
        }

    async def _tz(self, owner_user_id: str) -> str:
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        return user.time_zone