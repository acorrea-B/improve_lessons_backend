"""Reminder service (T045–T046, US-3, FR-016).

Five minutes before a scheduled session starts, an email is produced with
the session information and the modality-specific content (virtual: the
platform URL; in-person: the location). Failures are logged and contained
(constitution principle X); the feature gate (US-13) is consulted.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from app.core.entities.feature_availability import AuditEvent
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.email_sender import EmailSender
from app.core.ports.feature_availability_repository import FeatureAvailabilityRepository
from app.core.ports.platform_repository import PlatformRepository
from app.core.ports.session_repository import SessionRepository
from app.core.ports.user_repository import UserRepository
from app.core.strategies.submission_status_strategy import zone_for
from app.core.time.utc import now_utc, require_aware_utc
from app.utils.logging import get_logger, report_error, report_info

#: The reminder lead time: 5 minutes before the scheduled start.
from datetime import timedelta

REMINDER_LEAD = timedelta(minutes=5)

REMINDER_FEATURE = "reminders"

logger = get_logger("services.reminder")


class ReminderService:
    def __init__(
        self,
        sessions: SessionRepository,
        users: UserRepository,
        platforms: PlatformRepository,
        email_sender: EmailSender,
        audit_events: AuditEventRepository,
        feature_availability: FeatureAvailabilityRepository,
    ) -> None:
        self._sessions = sessions
        self._users = users
        self._platforms = platforms
        self._email = email_sender
        self._audit = audit_events
        self._features = feature_availability

    async def dispatch_due(self, now=None) -> int:
        """Produce the reminders due in the current scan window.

        Returns the number of emails produced. A disabled feature or a
        delivery failure never raises: they are contained and logged.
        """
        now = require_aware_utc(now if now is not None else now_utc())
        pending = await self._sessions.list_pending_reminders(
            window_start=now - REMINDER_LEAD,
            window_end=now + REMINDER_LEAD,
        )
        dispatches = 0
        for session in pending:
            user = await self._users.get_by_id(session.owner_user_id)
            if user is None:
                continue
            record = await self._features.get(REMINDER_FEATURE)
            if record is not None and not record.enabled:
                await self._audit.insert(
                    AuditEvent(
                        owner_user_id=str(user.id),
                        event_type="reminder.suppressed",
                        payload={
                            "session_id": str(session.id),
                            "time_zone": user.time_zone,
                        },
                    )
                )
                continue
            subject = f"Study reminder: {user.preferred_name or user.name}"
            from app.core.time.wall_clock import format_local

            local_start_text = format_local(session.scheduled_start_at, user.time_zone)
            from app.core.entities.enums import Modality

            if session.modality is Modality.VIRTUAL:
                detail = f"Your class link: {session.platform_url}"
            else:
                detail = f"Your class location: {session.location}"
            body = (
                f"Hello {user.preferred_name or user.name},\n\n"
                f"Your session starts at "
                f"{local_start_text}.\n{detail}"
            )
            try:
                await self._email.send(user.email, subject, body)
            except Exception as exc:
                # Contained failure: logged, never surfaced to the user.
                report_error(
                    "reminder.failed", "email dispatch failed",
                    session_id=str(session.id), error=str(exc)[:200],
                )
                await self._audit.insert(
                    AuditEvent(
                        owner_user_id=str(user.id),
                        event_type="reminder.failed",
                        payload={"session_id": str(session.id), "time_zone": user.time_zone},
                    )
                )
                continue
            session.reminder_sent_at = now
            await self._sessions.update(session)
            dispatches += 1
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=str(user.id),
                    event_type="reminder.dispatched",
                    payload={
                        "session_id": str(session.id),
                        "sent_at": now.isoformat(),
                        "time_zone": user.time_zone,
                    },
                )
            )
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=str(user.id),
                    event_type="reminder.scheduled",
                    payload={
                        "session_id": str(session.id),
                        "lead_minutes": 5,
                        "time_zone": user.time_zone,
                    },
                )
            )
            report_info(
                "reminder.dispatched", "reminder email produced",
                session_id=str(session.id),
            )
        return dispatches


class ReminderWorker:
    """Single in-process async loop behind the ``Scheduler`` port
    (T046; full worker infrastructure is a forward concern)."""

    def __init__(self, service: ReminderService, *, interval_seconds: float = 60) -> None:
        self._service = service
        self._interval = interval_seconds
        self._task = None
        self._stopping = False

    def start(self) -> None:
        import asyncio

        self._stopping = False

        async def _loop() -> None:
            while not self._stopping:
                try:
                    await self._service.dispatch_due()
                except Exception as exc:  # contained per constitution X
                    logger.error("reminder scan failed | error=%s", exc)
                await asyncio.sleep(self._interval)

        self._task = asyncio.get_event_loop().create_task(_loop())

    async def stop(self) -> None:
        import asyncio

        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, StopIteration):
                pass
            self._task = None