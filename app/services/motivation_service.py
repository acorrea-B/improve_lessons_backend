"""Motivation service (T099, US-11).

Recognitions are computed from the user's recorded history (via the
progress service); the recommended challenge uses the recommendation
strategy (CEFR + 1, FR-075). Challenge material is produced through the
two-model content workflow (US-12) on start.
"""

from __future__ import annotations

import uuid as uuid_module
from typing import TYPE_CHECKING

from app.core.entities.enums import CEFRLevel

from app.core.entities.feature_availability import AuditEvent
from app.core.entities.materials import GenerationInputs
from app.core.entities.motivation import Challenge, Recognition
from app.core.errors import NotFoundError
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.summary_repository import SummaryRepository
from app.core.ports.user_repository import UserRepository
from app.core.strategies.recommendation_strategy import (
    RecommendationStrategy,
    longest_on_time_streak,
    on_time_streak,
)
from app.core.time.utc import now_utc
from app.utils.logging import report_info

if TYPE_CHECKING:
    from app.services.content.content_workflow import ContentWorkflowService
    from app.services.progress_service import ProgressService

CHALLENGE_FEATURE = "challenges"


class MotivationService:
    def __init__(
        self,
        users: UserRepository,
        summaries: SummaryRepository,
        progress_service,
        recommendation_strategy: RecommendationStrategy,
        workflow: "ContentWorkflowService | None",
        audit_events: AuditEventRepository,
    ) -> None:
        self._users = users
        self._summaries = summaries
        self._progress = progress_service
        self._recommend = recommendation_strategy
        self._workflow = workflow
        self._audit = audit_events
        self._challenges: dict[str, Challenge] = {}  # in-memory for this release

    async def recognitions(
        self, owner_user_id: str
    ) -> list[Recognition]:
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        summaries = await self._summaries.list_for_owner(owner_user_id)
        statuses = [item.submission_status for item in summaries]
        streak = on_time_streak(statuses)
        best = longest_on_time_streak(statuses)
        recognitions: list[Recognition] = [
            Recognition(
                owner_user_id=owner_user_id,
                kind="on_time_streak",
                description=f"On-time streak: {streak} sessions.",
                streak=streak,
            )
        ]
        if best >= 5:
            recognitions.append(
                Recognition(
                    owner_user_id=owner_user_id,
                    kind="consistency",
                    description=f"Longest on-time streak: {best} sessions.",
                    streak=best,
                )
            )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="recognition.computed",
                payload={"count": len(recognitions), "streak": streak},
            )
        )
        return recognitions

    async def next_challenge(self, owner_user_id: str) -> Challenge:
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        summaries = await self._summaries.list_for_owner(owner_user_id)
        statuses = [item.submission_status for item in summaries]
        recent_on_time = on_time_streak(statuses)
        recommendation = self._recommend.recommend(
            declared_level=user.cefr_level,
            has_history=bool(summaries),
            recent_on_time_submissions=recent_on_time,
        )
        challenge = Challenge(
            owner_user_id=owner_user_id,
            target_cefr_level=recommendation.target_cefr_level.value,
            title=f"{recommendation.target_cefr_level.value} challenge",
            description=(
                f"Recommended challenge target: {recommendation.target_cefr_level.value}. "
                f"{recommendation.rationale}"
            ),
        )
        self._challenges[str(challenge.id)] = challenge
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="challenge.recommended",
                payload={
                    "target_cefr_level": challenge.target_cefr_level,
                    "kind": recommendation.kind,
                },
            )
        )
        return challenge

    async def start_challenge(
        self, owner_user_id: str, challenge_id: str
    ) -> Challenge:
        """Start a challenge: its material is generated through the
        standard two-model workflow (US-12); the challenge must exist and
        remain inside the CEFR + 1 bound."""
        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        challenge = self._challenges.get(challenge_id)
        if challenge is None or challenge.owner_user_id != owner_user_id:
            raise NotFoundError(
                "challenge_not_found", "No challenge with that id for this user."
            )
        # Enforce the CEFR + 1 bound at start (constitution VII).
        target = CEFRLevel(challenge.target_cefr_level)
        bound = user.cefr_level.next_level() or user.cefr_level
        if target > bound:
            target = bound
            challenge.target_cefr_level = bound.value
        challenge.started = True
        challenge.started_at = now_utc()
        if self._workflow is not None:
            inputs = GenerationInputs(
                cefr_level=challenge.target_cefr_level,
                purpose="progressive challenge material",
                history_slice=[],
                period_objective=challenge.title,
            )
            try:
                await self._workflow.produce(owner_user_id, "challenge material", inputs)
            except Exception as exc:
                from app.utils.logging import report_error

                report_error(
                    "challenge.material_failed",
                    "challenge material workflow failed (contained)",
                    error=str(exc)[:200],
                )
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="challenge.material_approved",
                    payload={"challenge_id": challenge_id},
                )
            )
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="challenge.material_delivered",
                    payload={"challenge_id": challenge_id},
                )
            )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="challenge.started",
                payload={"challenge_id": challenge_id},
            )
        )
        report_info(
            "challenge.started", "challenge started",
            challenge_id=challenge_id, target=challenge.target_cefr_level,
        )
        return challenge