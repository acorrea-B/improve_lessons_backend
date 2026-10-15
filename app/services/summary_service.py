"""Summary service (T052, US-4).

Enforces the immutable-learning-record rules (constitution principle IV):
append-only inserts, empty-content rejection, duplicate rejection per
session, and on-time/late computation at insert time via the
submission-status strategy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.entities.daily_summary import DailySummary
from app.core.entities.feature_availability import AuditEvent
from app.core.errors import ConflictError, NotFoundError, ValidationErrorDetail
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.session_repository import SessionRepository
from app.core.ports.summary_repository import SummaryRepository
from app.core.strategies.submission_status_strategy import SubmissionStatusStrategy
from app.core.time.utc import now_utc, require_aware_utc
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    pass

logger = get_logger("services.summary")


class SummaryService:
    def __init__(
        self,
        summaries: SummaryRepository,
        sessions: SessionRepository,
        audit_events: AuditEventRepository,
        status_strategy: SubmissionStatusStrategy,
    ) -> None:
        self._summaries = summaries
        self._sessions = sessions
        self._audit = audit_events
        self._status = status_strategy

    async def submit(
        self,
        owner_user_id: str,
        session_id: str,
        content: str,
        *,
        user_time_zone: str,
    ) -> DailySummary:
        if not content or not content.strip():
            raise ValidationErrorDetail(
                code="empty_content",
                message="The summary content must not be empty (FR-023).",
                details={"field": "content"},
            )
        session = await self._sessions.get(session_id, owner_user_id)
        if session is None:
            raise NotFoundError(
                "session_not_found", "No session with that id for this user."
            )
        existing = await self._summaries.get_by_session(session_id, owner_user_id)
        if existing is not None:
            # A late arrival can never silently delete or reclassify the
            # first record: the duplicate is rejected, the record kept.
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="summary.rejected_duplicate",
                    payload={
                        "session_id": session_id,
                        "time_zone": user_time_zone,
                        "first_submitted_at": existing.submitted_at.isoformat(),
                    },
                )
            )
            raise ConflictError(
                "summary_already_exists",
                "A summary for this session has already been submitted.",
            )
        submitted_at = now_utc()
        submitted = require_aware_utc(submitted_at, argument="submitted_at")
        status = self._status.derive(
            submitted_at=submitted,
            scheduled_start_at=session.scheduled_start_at,
            scheduled_end_at=session.scheduled_end_at,
        )
        before_start = self._status.submitted_before_start(
            submitted_at=submitted, scheduled_start_at=session.scheduled_start_at
        )
        summary = DailySummary(
            owner_user_id=owner_user_id,
            session_id=session_id,
            content=content.strip(),
            submitted_at=submitted,
            submission_status=status,
            submitted_before_session_start=before_start,
        )
        await self._summaries.insert(summary)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="summary.submitted",
                payload={
                    "session_id": session_id,
                    "submitted_at": submitted.isoformat(),
                    "submission_status": status.value,
                    "time_zone": user_time_zone,
                    "inputs": {
                        "scheduled_end_at": session.scheduled_end_at.isoformat(),
                        "window_minutes": 30,
                    },
                },
            )
        )
        report_info(
            "summary.submitted", "summary stored",
            session_id=session_id, status=status.value,
        )
        return summary

    async def get(self, owner_user_id: str, summary_id: str) -> DailySummary:
        summary = await self._summaries.get(summary_id, owner_user_id)
        if summary is None:
            raise NotFoundError(
                "summary_not_found", "No summary with that id for this user."
            )
        return summary

    async def get_by_session(self, owner_user_id: str, session_id: str) -> DailySummary | None:
        return await self._summaries.get_by_session(session_id, owner_user_id)

    async def list_in_range(
        self,
        owner_user_id: str,
        from_instant,
        to_instant,
    ) -> list[DailySummary]:
        return await self._summaries.list_for_owner(
            owner_user_id,
            from_instant=require_aware_utc(from_instant),
            to_instant=require_aware_utc(to_instant),
        )