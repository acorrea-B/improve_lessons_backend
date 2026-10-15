"""Weekly and monthly rollup services (T070/T076, US-6, US-7).

- Weekly: consumes sessions + summaries in the Monday→Monday window in the
  user's tz (``week_boundary_strategy``) and produces the consolidated
  ``WeeklySummary`` plus the approved ``weekly_material`` (US-12 gate).
- Monthly: consumes the ``weekly_summary_repository`` rows whose weeks
  start within the calendar month (``month_boundary_strategy``).

Rollups are computed deterministically and idempotently: calling the
service twice for the same period returns the persisted summary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.entities.feature_availability import AuditEvent
from app.core.entities.materials import (
    GenerationInputs,
    MonthlyMaterial,
    MonthlySummary,
    ReadingContent,
    WeeklyMaterial,
    WeeklySummary,
    WritingExercise,
)
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.monthly_material_repository import MonthlyMaterialRepository
from app.core.ports.monthly_summary_repository import MonthlySummaryRepository
from app.core.ports.session_repository import SessionRepository
from app.core.ports.summary_repository import SummaryRepository
from app.core.ports.user_repository import UserRepository
from app.core.ports.weekly_material_repository import WeeklyMaterialRepository
from app.core.ports.weekly_summary_repository import WeeklySummaryRepository
from app.core.strategies.month_boundary_strategy import (
    month_end_for_wall_clock,
    month_start_for_wall_clock,
)
from app.core.strategies.week_boundary_strategy import week_end_for_wall_clock
from app.core.strategies.recommendation_strategy import (
    longest_on_time_streak,
    on_time_streak,
)
from app.core.time.utc import now_utc, require_aware_utc
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    from app.services.content.content_workflow import ContentWorkflowService
    from app.services.feature_availability_service import FeatureAvailabilityService

logger = get_logger("services.rollup")


def _consistency_indicators(
    on_time: int, late: int, missing: int, statuses: list
) -> dict:
    return {
        "on_time_count": on_time,
        "late_count": late,
        "missing_count": missing,
        "current_on_time_streak": on_time_streak(statuses),
        "longest_on_time_streak": longest_on_time_streak(statuses),
    }


def _knowledge_synthesis(summaries: list, max_chars: int = 1200) -> str:
    """Natural-language synthesis of the documented week/month concepts."""
    if not summaries:
        return "No learning records were documented in this period."
    bullet_points = []
    budget = max_chars
    for summary in summaries[-20:]:
        first_sentence = summary.content.split(". ")[0][:180]
        bullet_points.append(f"- {first_sentence}")
        budget -= len(first_sentence) + 2
        if budget <= 0:
            break
    return "Concepts documented in this period:\n" + "\n".join(bullet_points)


class WeeklyRollupService:
    def __init__(
        self,
        summaries: SummaryRepository,
        sessions: SessionRepository,
        users: UserRepository,
        weekly_summaries: WeeklySummaryRepository,
        weekly_materials: WeeklyMaterialRepository,
        workflow: "ContentWorkflowService",
        audit_events: AuditEventRepository,
        features: "FeatureAvailabilityService | None" = None,
    ) -> None:
        self._summaries = summaries
        self._sessions = sessions
        self._users = users
        self._weekly_summaries = weekly_summaries
        self._weekly_materials = weekly_materials
        self._workflow = workflow
        self._audit = audit_events
        self._features = features

    async def compute(self, owner_user_id: str, trigger_instant=None) -> WeeklySummary:
        """Roll up the week containing the trigger date (or now)."""
        trigger = require_aware_utc(trigger_instant if trigger_instant is not None else now_utc())
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        from app.core.strategies.week_boundary_strategy import week_start_for_wall_clock

        week_start = week_start_for_wall_clock(trigger, user.time_zone)
        week_end = week_end_for_wall_clock(week_start, user.time_zone)

        persisted = await self._weekly_summaries.get_by_period(owner_user_id, week_start)
        if persisted is not None:
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="weekly_summary.computed",
                    payload={"week_start_at": week_start.isoformat(), "cached": True},
                )
            )
            return persisted

        sessions = await self._sessions.list_for_owner(
            owner_user_id, from_instant=week_start, to_instant=week_end
        )
        summaries = await self._summaries.list_for_owner(
            owner_user_id, from_instant=week_start, to_instant=week_end
        )
        by_session = {item.session_id: item for item in summaries}
        on_time = sum(1 for item in summaries if item.submission_status.value == "on_time")
        late = sum(1 for item in summaries if item.submission_status.value == "late")
        finished = [session for session in sessions if session.scheduled_end_at <= now_utc()]
        missing = sum(1 for session in finished if session.schedule_id and str(session.id) not in by_session)
        recorded_minutes = sum(
            int((session.scheduled_end_at - session.scheduled_start_at).total_seconds() // 60)
            for key, session in [(str(session.id), session) for session in sessions]
            if key in by_session
        )
        rollout = WeeklySummary(
            owner_user_id=owner_user_id,
            week_start_at=week_start,
            week_end_at=week_end,
            on_time_count=on_time,
            late_count=late,
            missing_count=missing,
            recorded_study_minutes=recorded_minutes,
            consistency_indicators=_consistency_indicators(on_time, late, missing, [item.submission_status for item in summaries]),
            knowledge_synthesis=_knowledge_synthesis(summaries),
        )
        await self._weekly_summaries.insert(rollout)
        await self._maybe_generate_material(owner_user_id, rollout, user.time_zone)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="weekly_summary.computed",
                payload={
                    "week_start_at": week_start.isoformat(),
                    "on_time": on_time,
                    "late": late,
                    "missing": missing,
                },
            )
        )
        return rollout

    async def _maybe_generate_material(
        self, owner_user_id: str, rollout: WeeklySummary, time_zone: str
    ) -> None:
        from app.core.strategies.week_boundary_strategy import week_start_for_wall_clock

        try:
            inputs = GenerationInputs(
                cefr_level=(await self._users.get_by_id(owner_user_id)).cefr_level.value,
                purpose="weekly review material",
                history_slice=[rollout.knowledge_synthesis[:400]],
                period_objective=f"Week starting {rollout.week_start_at.isoformat()} review",
            )
            result = await self._workflow.produce(owner_user_id, "weekly review material", inputs)
            if not result.approved or result.generation is None:
                return
            payload = result.generation.payload
            material = WeeklyMaterial(
                owner_user_id=owner_user_id,
                weekly_summary_id=str(rollout.id),
                reading=ReadingContent(**payload["reading"]),
                writing_exercises=[
                    WritingExercise(**exercise) for exercise in payload["writing_exercises"]
                ],
                generation_id=result.generation_id,
                evaluation_id=result.evaluation_id,
                approved_at=now_utc(),
            )
            await self._weekly_materials.update(material)
            rollout.weekly_material_id = str(material.id)
            await self._weekly_summaries.update(rollout)
            for event_type, body in (
                ("weekly_material.approved", {"material_id": str(material.id)}),
                ("weekly_material.delivered", {"material_id": str(material.id)}),
            ):
                await self._audit.insert(
                    AuditEvent(owner_user_id=owner_user_id, event_type=event_type, payload=body)
                )
        except Exception as exc:  # contained per constitution principle X
            logger.error("weekly material generation failed | error=%s", exc)

    async def get_or_404(self, owner_user_id: str, summary_id: str) -> WeeklySummary:
        summary = await self._weekly_summaries.get(summary_id, owner_user_id)
        if summary is None:
            raise NotFoundError("weekly_summary_not_found", "No weekly summary with that id.")
        return summary

    async def list_in_range(self, owner_user_id: str, *, from_instant, to_instant) -> list[WeeklySummary]:
        return await self._weekly_summaries.list_for_owner(
            owner_user_id, from_instant=from_instant, to_instant=to_instant
        )


class MonthlyRollupService:
    def __init__(
        self,
        weekly_summaries: WeeklySummaryRepository,
        monthly_summaries: MonthlySummaryRepository,
        monthly_materials: MonthlyMaterialRepository,
        users: UserRepository,
        workflow: "ContentWorkflowService",
        audit_events: AuditEventRepository,
        weekly_rollup_service=None,
    ) -> None:
        self._weekly_rollup_service = weekly_rollup_service
        self._weekly = weekly_summaries
        self._monthly_summaries = monthly_summaries
        self._monthly_materials = monthly_materials
        self._users = users
        self._workflow = workflow
        self._audit = audit_events

    async def compute(self, owner_user_id: str, trigger_instant=None) -> MonthlySummary:
        trigger = require_aware_utc(trigger_instant if trigger_instant is not None else now_utc())
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        month_start = month_start_for_wall_clock(trigger, user.time_zone)
        month_end = month_end_for_wall_clock(month_start, user.time_zone)

        persisted = await self._monthly_summaries.get_by_period(owner_user_id, month_start)
        if persisted is not None:
            return persisted

        weeks = await self._weekly.list_for_owner(
            owner_user_id, from_instant=month_start, to_instant=month_end
        )
        if not weeks:
            # The week-level rollups do not exist yet: compute them now
            # (idempotent) so the monthly aggregation consumes their rows.
            if self._weekly_rollup_service is not None:
                for week_start in _week_starts_between(
                    month_start, month_end, user.time_zone
                ):
                    await self._weekly_rollup_service._compute_at_week_start(
                        owner_user_id, week_start, user.time_zone
                    )
                weeks = await self._weekly.list_for_owner(
                    owner_user_id, from_instant=month_start, to_instant=month_end
                )
        on_time = sum(week.on_time_count for week in weeks)
        late = sum(week.late_count for week in weeks)
        missing = sum(week.missing_count for week in weeks)
        recorded_minutes = sum(week.recorded_study_minutes for week in weeks)
        from app.core.entities.enums import SubmissionStatus

        statuses: list = [SubmissionStatus.ON_TIME] * on_time
        statuses += [SubmissionStatus.LATE] * late
        synthesis = "\n".join(week.knowledge_synthesis for week in weeks if week.knowledge_synthesis)
        rollout = MonthlySummary(
            owner_user_id=owner_user_id,
            month_start_at=month_start,
            month_end_at=month_end,
            on_time_count=on_time,
            late_count=late,
            missing_count=missing,
            recorded_study_minutes=recorded_minutes,
            consistency_indicators=_consistency_indicators(on_time, late, missing, statuses),
            knowledge_synthesis=synthesis or "No weekly synthesis recorded for this month.",
        )
        await self._monthly_summaries.insert(rollout)
        await self._maybe_generate_material(owner_user_id, rollout)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="monthly_summary.computed",
                payload={"month_start_at": month_start.isoformat()},
            )
        )
        return rollout

    async def _maybe_generate_material(self, owner_user_id: str, rollout: MonthlySummary) -> None:
        try:
            user = await self._users.get_by_id(owner_user_id)
            inputs = GenerationInputs(
                cefr_level=user.cefr_level.value,
                purpose="monthly review material",
                history_slice=[rollout.knowledge_synthesis[:400]],
                period_objective=f"Month starting {rollout.month_start_at.isoformat()} review",
            )
            result = await self._workflow.produce(owner_user_id, "monthly review material", inputs)
            if not result.approved or result.generation is None:
                return
            payload = result.generation.payload
            material = MonthlyMaterial(
                owner_user_id=owner_user_id,
                monthly_summary_id=str(rollout.id),
                reading=ReadingContent(**payload["reading"]),
                writing_exercises=[
                    WritingExercise(**exercise) for exercise in payload["writing_exercises"]
                ],
                generation_id=result.generation_id,
                evaluation_id=result.evaluation_id,
                approved_at=now_utc(),
            )
            await self._monthly_materials.update(material)
            rollout.monthly_material_id = str(material.id)
            await self._monthly_summaries.update(rollout)
            for event_type, body in (
                ("monthly_material.approved", {"material_id": str(material.id)}),
                ("monthly_material.delivered", {"material_id": str(material.id)}),
            ):
                await self._audit.insert(
                    AuditEvent(owner_user_id=owner_user_id, event_type=event_type, payload=body)
                )
        except Exception as exc:  # contained per constitution principle X
            logger.error("monthly material generation failed | error=%s", exc)

    async def get_or_404(self, owner_user_id: str, summary_id: str) -> MonthlySummary:
        summary = await self._monthly_summaries.get(summary_id, owner_user_id)
        if summary is None:
            raise NotFoundError("monthly_summary_not_found", "No monthly summary with that id.")
        return summary

    async def list_in_range(self, owner_user_id: str, *, from_instant, to_instant) -> list[MonthlySummary]:
        return await self._monthly_summaries.list_for_owner(
            owner_user_id, from_instant=from_instant, to_instant=to_instant
        )



def _week_starts_between(start, end, time_zone: str) -> list:
    """Every week_start in [start, end) for the user's tz."""
    from app.core.strategies.week_boundary_strategy import week_start_for_wall_clock

    cursor = week_start_for_wall_clock(start, time_zone)
    week_starts = []
    while cursor < end:
        week_starts.append(cursor)
        cursor = week_end_for_wall_clock(cursor, time_zone)
    return week_starts


def _month_starts_between(start, end, time_zone: str) -> list:
    from app.core.strategies.month_boundary_strategy import month_start_for_wall_clock
    from datetime import datetime as _datetime

    from app.core.strategies.submission_status_strategy import zone_for
    from app.core.time.utc import normalize_to_utc

    cursor = month_start_for_wall_clock(start, time_zone)
    month_starts = []
    while cursor < end:
        month_starts.append(cursor)
        year, month = cursor.year, cursor.month
        next_month = 1 if month == 12 else month + 1
        next_year = year + 1 if month == 12 else year
        cursor = normalize_to_utc(
            _datetime(next_year, next_month, 1, tzinfo=zone_for(time_zone))
        )
    return month_starts


def _period_range_methods():
    """compute_range implementations binding the period boundary helpers."""
    return {}


async def weekly_compute_range(self, owner_user_id: str, start, end) -> list[WeeklySummary]:
    """Roll up every week starting within [start, end) (idempotent)."""
    user = await self._users.get_by_id(owner_user_id)
    if user is None:
        raise NotFoundError("user_not_found", "No user for the authenticated principal.")
    summaries = []
    for week_start in _week_starts_between(start, end, user.time_zone):
        persisted = await self._weekly_summaries.get_by_period(owner_user_id, week_start)
        summaries.append(persisted if persisted is not None else await self._compute_at_week_start(owner_user_id, week_start, user.time_zone))
    await self._audit.insert(
        AuditEvent(
            owner_user_id=owner_user_id,
            event_type="weekly_summary.requested",
            payload={"weeks": len(summaries), "time_zone": user.time_zone},
        )
    )
    return summaries


async def weekly_compute_at_week_start(self, owner_user_id: str, week_start, time_zone: str) -> WeeklySummary:
    """compute(week_start) without re-deriving the week from an instant."""
    week_end = week_end_for_wall_clock(week_start, time_zone)
    persisted = await self._weekly_summaries.get_by_period(owner_user_id, week_start)
    if persisted is not None:
        return persisted
    summaries = await self._summaries.list_for_owner(
        owner_user_id, from_instant=week_start, to_instant=week_end
    )
    sessions = await self._sessions.list_for_owner(
        owner_user_id, from_instant=week_start, to_instant=week_end
    )
    by_session = {item.session_id for item in summaries}
    on_time = sum(1 for item in summaries if item.submission_status.value == "on_time")
    late = sum(1 for item in summaries if item.submission_status.value == "late")
    finished = [session for session in sessions if session.scheduled_end_at <= now_utc()]
    missing = sum(1 for session in finished if str(session.id) not in by_session)
    recorded_minutes = sum(
        int((session.scheduled_end_at - session.scheduled_start_at).total_seconds() // 60)
        for session in sessions
        if str(session.id) in by_session
    )
    rollout = WeeklySummary(
        owner_user_id=owner_user_id,
        week_start_at=week_start,
        week_end_at=week_end,
        on_time_count=on_time,
        late_count=late,
        missing_count=missing,
        recorded_study_minutes=recorded_minutes,
        consistency_indicators=_consistency_indicators(
            on_time, late, missing, [item.submission_status for item in summaries]
        ),
        knowledge_synthesis=_knowledge_synthesis(summaries),
    )
    await self._weekly_summaries.insert(rollout)
    await self._maybe_generate_material(owner_user_id, rollout, time_zone)
    await self._audit.insert(
        AuditEvent(
            owner_user_id=owner_user_id,
            event_type="weekly_summary.computed",
            payload={"week_start_at": week_start.isoformat(), "time_zone": time_zone},
        )
    )
    return rollout


async def monthly_compute_range(self, owner_user_id: str, start, end) -> list[MonthlySummary]:
    """Roll up every calendar month starting within [start, end)."""
    user = await self._users.get_by_id(owner_user_id)
    if user is None:
        raise NotFoundError("user_not_found", "No user for the authenticated principal.")
    summaries = []
    for month_start in _month_starts_between(start, end, user.time_zone):
        persisted = await self._monthly_summaries.get_by_period(owner_user_id, month_start)
        if persisted is None:
            persisted = await self.compute(owner_user_id, trigger_instant=month_start)
        summaries.append(persisted)
    await self._audit.insert(
        AuditEvent(
            owner_user_id=owner_user_id,
            event_type="monthly_summary.requested",
            payload={"months": len(summaries), "time_zone": user.time_zone},
        )
    )
    return summaries


# Bind the compute_range implementations to the concrete services.
# (Kept as module-level functions above to avoid duplicating the window
# helpers; constitution principle IX keeps them in this same module.)
WeeklyRollupService.compute_range = weekly_compute_range  # type: ignore[attr-defined]
WeeklyRollupService._compute_at_week_start = weekly_compute_at_week_start  # type: ignore[attr-defined]
MonthlyRollupService.compute_range = monthly_compute_range  # type: ignore[attr-defined]
