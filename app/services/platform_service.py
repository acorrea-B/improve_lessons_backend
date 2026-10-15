"""Platform + schedule services (T040, US-2).

The schedule service expands schedules into concrete sessions
deterministically in the user's time zone; the expansion is recomputed on
every change (data-model.md § schedules).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.core.entities.enums import Modality, Recurrence
from app.core.entities.external_learning_platform import ExternalLearningPlatform
from app.core.entities.feature_availability import AuditEvent
from app.core.entities.schedule import Schedule
from app.core.entities.session import Session
from app.core.errors import ConflictError, NotFoundError, ValidationErrorDetail
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.platform_repository import PlatformRepository
from app.core.ports.schedule_repository import ScheduleRepository
from app.core.ports.session_repository import SessionRepository
from app.core.ports.user_repository import UserRepository
from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import normalize_to_utc, now_utc, require_aware_utc
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    from app.core.ports.clock import Clock

#: Look-ahead window when expanding a schedule into sessions (days).
SESSION_HORIZON_DAYS = 30

logger = get_logger("services.schedule")


class PlatformService:
    def __init__(
        self,
        platforms: PlatformRepository,
        schedules: ScheduleRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self._platforms = platforms
        self._schedules = schedules
        self._audit = audit_events

    async def register(self, owner_user_id: str, name: str, url: str) -> ExternalLearningPlatform:
        if not name.strip():
            raise ValidationErrorDetail(
                code="invalid_platform_name", message="name must not be empty.",
                details={"field": "name"},
            )
        if not url.strip():
            raise ValidationErrorDetail(
                code="invalid_platform_url", message="url must not be empty.",
                details={"field": "url"},
            )
        platform = ExternalLearningPlatform(
            owner_user_id=owner_user_id, name=name.strip(), url=url.strip()
        )
        await self._platforms.insert(platform)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="platform.registered",
                payload={"platform_id": str(platform.id), "name": platform.name},
            )
        )
        return platform

    async def list(self, owner_user_id: str) -> list[ExternalLearningPlatform]:
        return await self._platforms.list_for_owner(owner_user_id)

    async def get(self, owner_user_id: str, platform_id: str) -> ExternalLearningPlatform:
        platform = await self._platforms.get(platform_id, owner_user_id)
        if platform is None:
            raise NotFoundError(
                "platform_not_found", "No platform with that id for this user."
            )
        return platform

    async def remove(self, owner_user_id: str, platform_id: str) -> None:
        await self.get(owner_user_id, platform_id)
        in_use = any(
            schedule.platform_id == platform_id
            for schedule in await self._schedules.list_for_owner(owner_user_id)
        )
        if in_use:
            raise ConflictError(
                "platform_in_use",
                "A schedule still references this platform.",
                details={"field": "platform_id"},
            )
        await self._platforms.delete(platform_id, owner_user_id)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="platform.removed",
                payload={"platform_id": platform_id},
            )
        )


def _wall_clock_on_date(time_zone: str, day, hhmm: str) -> datetime:
    """Resolve a local wall-clock HH:MM on *day* to a UTC instant (DST-safe)."""
    from app.core.time.wall_clock import utc_from_wall_clock

    return utc_from_wall_clock(day, hhmm, time_zone)


def expand_schedule(
    schedule: Schedule,
    user_time_zone: str,
    *,
    clock: "Clock | None" = None,
    horizon_days: int = SESSION_HORIZON_DAYS,
) -> list[Session]:
    """Expand a schedule into Sessions (deterministic, user's tz)."""
    now = now_utc() if clock is None else clock.now()
    step = 1 if schedule.recurrence.value == "daily" else 2

    zone = zone_for(user_time_zone)
    from app.core.time.wall_clock import wall_clock_in_zone

    today_local = wall_clock_in_zone(now, user_time_zone)
    sessions: list[Session] = []
    for offset in range(0, horizon_days, step):
        if offset == 0:
            # Include the just-elapsed day so sessions ending slightly in the
            # past remain summarizable within the 30-minute window, and
            # rollups can count missing sessions (FR-027).
            day = (today_local - timedelta(days=1)).date()
        else:
            day = (today_local + timedelta(days=offset - 1)).date()
        start = _wall_clock_on_date(user_time_zone, day, schedule.start_time)
        end = _wall_clock_on_date(user_time_zone, day, schedule.end_time)
        if end <= start:
            # Overnight session (e.g. 22:00 → 01:00) rolls into the next day.
            end += timedelta(days=1)
        if end < now - timedelta(hours=24):
            continue  # older than the summarizable window
        if end <= now and (start > now - timedelta(hours=24)):
            pass  # recently ended: retained for the on-time/late window
        sessions.append(
            Session(
                owner_user_id=schedule.owner_user_id,
                schedule_id=str(schedule.id),
                scheduled_start_at=start,
                scheduled_end_at=end,
                modality=schedule.modality,
                platform_id=schedule.platform_id,
                platform_url=schedule.platform_url,
                location=schedule.location,
            )
        )
    return sessions


class ScheduleService:
    def __init__(
        self,
        schedules: ScheduleRepository,
        platforms: PlatformRepository,
        sessions: SessionRepository,
        users: UserRepository,
        audit_events: AuditEventRepository,
        clock: "Clock",
    ) -> None:
        self._schedules = schedules
        self._platforms = platforms
        self._sessions = sessions
        self._users = users
        self._audit = audit_events
        self._clock = clock

    async def create(self, owner_user_id: str, data: dict) -> Schedule:
        schedule = await self._build(owner_user_id, data, Schedule)
        await self._schedules.insert(schedule)
        await self._expand(schedule)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="schedule.created",
                payload={"schedule_id": str(schedule.id), "time_zone": await self._tz(owner_user_id)},
            )
        )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="sessions.expanded",
                payload={"schedule_id": str(schedule.id)},
            )
        )
        return schedule

    async def update(self, owner_user_id: str, schedule_id: str, changes: dict) -> Schedule:
        existing = await self._get(owner_user_id, schedule_id)
        data = {
            "start_time": getattr(existing, "start_time"),
            "end_time": getattr(existing, "end_time"),
            "recurrence": getattr(existing, "recurrence").value,
            "modality": getattr(existing, "modality").value,
            "platform_id": getattr(existing, "platform_id"),
            "platform_url": getattr(existing, "platform_url"),
            "location": getattr(existing, "location"),
        }
        data.update({key: value for key, value in changes.items() if key in data})
        updated = await self._build(owner_user_id, data, Schedule, id=existing.id, created_at=existing.created_at)
        # Edits apply to future sessions only (FR-014): drop future sessions
        # of this schedule, keep historical ones untouched.
        await self._sessions.delete_future_for_schedule(schedule_id, now_utc())
        await self._schedules.update(updated)
        await self._expand(updated)
        return updated

    async def delete(self, owner_user_id: str, schedule_id: str) -> None:
        schedule = await self._get(owner_user_id, schedule_id)
        removed = await self._sessions.delete_future_for_schedule(schedule_id, now_utc())
        await self._schedules.delete(schedule_id, owner_user_id)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="schedule.deleted",
                payload={"schedule_id": schedule_id, "future_sessions_removed": removed},
            )
        )

    async def get(self, owner_user_id: str, schedule_id: str) -> Schedule:
        return await self._get(owner_user_id, schedule_id)

    async def list(self, owner_user_id: str) -> list[Schedule]:
        return await self._schedules.list_for_owner(owner_user_id)

    async def _build(
        self, owner_user_id: str, data: dict, schema: type[Schedule], **overrides
    ) -> Schedule:
        modality = Modality(data["modality"])
        platform_id = data.get("platform_id")
        location = data.get("location")
        if modality is Modality.VIRTUAL:
            if not platform_id:
                raise ValidationErrorDetail(
                    code="invalid_schedule",
                    message="A virtual schedule must reference a platform (FR-011).",
                    details={"field": "platform_id"},
                )
            platform = await self._platforms.get(str(platform_id), owner_user_id)
            if platform is None:
                raise NotFoundError(
                    "platform_not_found", "The referenced platform does not exist."
                )
            data["platform_url"] = platform.url
            data["location"] = None
        else:
            if not location or not str(location).strip():
                raise ValidationErrorDetail(
                    code="invalid_schedule",
                    message="An in-person schedule must carry a location (FR-011).",
                    details={"field": "location"},
                )
            data["platform_id"] = None
            data["platform_url"] = None
        owner = await self._users.get_by_id(owner_user_id)
        if owner is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        payload = {
            "owner_user_id": owner_user_id,
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "recurrence": data["recurrence"],
            "modality": modality.value,
            "platform_id": data.get("platform_id"),
            "platform_url": data.get("platform_url"),
            "location": data.get("location"),
            "created_at": overrides.pop("created_at", now_utc()),
            "updated_at": now_utc(),
        }
        return self._rebuild(schema, payload, **{"id": overrides.get("id")} if overrides else {})

    def _rebuild(self, schema: type[Schedule], payload: dict, **explicit):
        fields = {key: value for key, value in payload.items() if key in schema.model_fields}
        extras = {
            key: value
            for key, value in explicit.items()
            if value is not None and key in schema.model_fields
        }
        fields.update(extras)
        return schema(**fields)

    async def _expand(self, schedule: Schedule) -> None:
        owner = await self._users.get_by_id(schedule.owner_user_id)
        sessions = expand_schedule(schedule, owner.time_zone, clock=self._clock)
        await self._sessions.insert_many(sessions)
        logger.info(
            "sessions expanded | schedule_id=%s count=%d", str(schedule.id), len(sessions)
        )

    async def _tz(self, owner_user_id: str) -> str:
        owner = await self._users.get_by_id(owner_user_id)
        return owner.time_zone if owner else "UTC"

    async def _get(self, owner_user_id: str, schedule_id: str) -> Schedule:
        schedule = await self._schedules.get(schedule_id, owner_user_id)
        if schedule is None:
            raise NotFoundError(
                "schedule_not_found", "No schedule with that id for this user."
            )
        return schedule