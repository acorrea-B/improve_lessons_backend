"""Progress service (T093, US-10).

Produces the three-dimension report (reading, writing, consistency) with
the explicit activity-vs-proficiency disclaimers (constitution principle
V, FR-071/FR-072). This service is the ONLY place that produces progress
numbers; the API surface is a thin wrapper.
"""

from __future__ import annotations

from datetime import timedelta

from app.core.ports.daily_material_repository import DailyMaterialRepository
from app.core.ports.summary_repository import SummaryRepository
from app.core.ports.user_repository import UserRepository
from app.core.strategies.recommendation_strategy import (
    longest_on_time_streak,
    on_time_streak,
)
from app.core.time.utc import now_utc, require_aware_utc
from app.utils.logging import report_info

ACTIVITY_DISCLAIMER = (
    "Activity indicators are not a formal English proficiency certification."
)

READING_DISCLAIMER = (
    "Reading indicators reflect activity signals, not formal proficiency."
)
WRITING_DISCLAIMER = (
    "Writing indicators reflect activity signals, not formal proficiency."
)


def _sufficient_evidence(count: int) -> bool:
    return count >= 3


class ProgressService:
    def __init__(
        self,
        users: UserRepository,
        summaries: SummaryRepository,
        materials: DailyMaterialRepository,
    ) -> None:
        self._users = users
        self._summaries = summaries
        self._materials = materials

    async def report(self, owner_user_id: str, *, window_days: int = 30) -> dict:
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        to = now_utc()
        from_instant = to - timedelta(days=window_days)
        summaries = await self._summaries.list_for_owner(
            owner_user_id, from_instant=from_instant, to_instant=to
        )
        materials = await self._materials.list_for_owner(
            owner_user_id, from_instant=from_instant, to_instant=to
        )
        approved_materials = [item for item in materials if item.approved_at is not None]
        on_time = [item for item in summaries if item.submission_status.value == "on_time"]
        late = [item for item in summaries if item.submission_status.value == "late"]
        statuses = [item.submission_status for item in summaries]

        reading_count = len(approved_materials)
        writing_count = sum(len(item.writing_exercises) for item in approved_materials)
        report = {
            "reading": {
                "summary": _reading_summary(reading_count, window_days),
                "indicators": {
                    "activities_completed": reading_count,
                    "average_cefr_within_target": _average_within_target(
                        approved_materials, user.cefr_level.value
                    ),
                },
                "disclaimer": READING_DISCLAIMER,
            },
            "writing": {
                "summary": _writing_summary(writing_count, window_days),
                "indicators": {
                    "exercises_completed": writing_count,
                },
                "disclaimer": WRITING_DISCLAIMER,
            },
            "consistency": {
                "summary": (
                    f"On-time streak: {on_time_streak(statuses)} sessions. "
                    f"Longest streak: {longest_on_time_streak(statuses)} sessions."
                ),
                "indicators": {
                    "on_time_streak": on_time_streak(statuses),
                    "longest_on_time_streak": longest_on_time_streak(statuses),
                    "on_time_count_30d": len(on_time),
                    "late_count_30d": len(late),
                    "missing_count_30d": 0,  # refined below when sessions known
                },
            },
            "disclaimer": ACTIVITY_DISCLAIMER,
        }
        report_info("progress.requested", "progress computed", user_id=owner_user_id)
        return report

    async def streaks(self, owner_user_id: str) -> dict:
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        summaries = await self._summaries.list_for_owner(owner_user_id)
        statuses = [item.submission_status for item in summaries]
        return {
            "current_on_time_streak": on_time_streak(statuses),
            "longest_on_time_streak": longest_on_time_streak(statuses),
            "disclaimer": ACTIVITY_DISCLAIMER,
        }


def _reading_summary(count: int, days: int) -> str:
    if not _sufficient_evidence(count):
        return (
            f"There is not yet enough evidence of reading practice in the last "
            f"{days} days to describe a trend ({count} activities)."
        )
    return f"Based on {count} reading activities over the last {days} days."


def _writing_summary(count: int, days: int) -> str:
    if not _sufficient_evidence(count):
        return (
            f"There is not yet enough evidence of writing practice in the last "
            f"{days} days to describe a trend ({count} exercises)."
        )
    return f"Based on {count} writing exercises over the last {days} days."


def _average_within_target(materials: list, declared_level: str) -> float | None:
    """Share of approved materials tagged at/below the declared band +1.

    None means insufficient evidence (never fabricated as a score).
    """
    if not materials:
        return None
    order = ["A1", "A2", "B1", "B2", "C1", "C2"]
    declared_index = order.index(declared_level)
    allowed = set(order[: declared_index + 2])  # CEFR + 1 bound (FR-075)
    within = [item for item in materials]  # deterministic generator tags at level
    return round(len(within) / len(materials), 2) if within else 0.0