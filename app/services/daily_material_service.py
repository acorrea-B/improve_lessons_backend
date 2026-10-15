"""Daily material service (T064, US-5).

Wires the summary service (US-4) to the content workflow (US-12) and
persists the approved material. The approval gate is never bypassed: the
service only persists a material carrying an ``approved`` evaluation id
(FR-046: once approved and persisted, repeated fetches return the same
material and do NOT trigger a new corrective-loop run).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.core.entities.feature_availability import AuditEvent
from app.core.entities.materials import (
    DailyMaterial,
    GenerationInputs,
    ReadingContent,
    WritingExercise,
)
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.daily_material_repository import DailyMaterialRepository
from app.core.ports.summary_repository import SummaryRepository
from app.core.time.utc import now_utc
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    from app.core.entities.daily_summary import DailySummary
    from app.services.content.content_workflow import ContentWorkflowService

logger = get_logger("services.daily_material")

#: Size of the documented-history slice fed to the generation model.
HISTORY_SLICE_SIZE = 5


class DailyMaterialService:
    def __init__(
        self,
        materials: DailyMaterialRepository,
        summaries: SummaryRepository,
        workflow: "ContentWorkflowService",
        audit_events: AuditEventRepository,
    ) -> None:
        self._materials = materials
        self._summaries = summaries
        self._workflow = workflow
        self._audit = audit_events

    async def request_material(
        self,
        owner_user_id: str,
        summary: "DailySummary",
        *,
        cefr_level: str,
    ) -> DailyMaterial:
        """Return the approved material for a summary (FR-046 contract)."""
        existing = await self._materials.get_by_summary(str(summary.id), owner_user_id)
        if existing is not None and existing.approved_at is not None:
            return existing  # served from cache; no new evaluation rows
        if existing is not None:
            # A previous attempt was not approved: the documented recovery
            # path re-runs the workflow and replaces the record on approval.
            return await self._produce_and_persist(owner_user_id, summary, cefr_level)

        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="daily_material.requested",
                payload={"summary_id": str(summary.id)},
            )
        )
        return await self._produce_and_persist(owner_user_id, summary, cefr_level)

    async def _produce_and_persist(
        self, owner_user_id: str, summary: "DailySummary", cefr_level: str
    ) -> DailyMaterial:
        recent = await self._summaries.list_for_owner(owner_user_id)
        history_slice = [item.content[:200] for item in recent[-HISTORY_SLICE_SIZE:]]
        inputs = GenerationInputs(
            cefr_level=cefr_level,
            purpose="daily reading and writing practice",
            history_slice=history_slice,
            period_objective="reinforce what was documented today",
        )
        result = await self._workflow.produce(owner_user_id, "daily practice", inputs)
        if not result.approved or result.generation is None:
            # Contained failure raised by the workflow; never fabricate a
            # material without an approved evaluation (FR-042).
            raise ServiceUnavailableError(
                "content_workflow_failed",
                "No approved material could be produced yet; try again later.",
            )
        payload = result.generation.payload
        material = DailyMaterial(
            owner_user_id=owner_user_id,
            summary_id=str(summary.id),
            reading=ReadingContent(**payload["reading"]),
            writing_exercises=[
                WritingExercise(**exercise) for exercise in payload["writing_exercises"]
            ],
            generation_id=result.generation_id,
            evaluation_id=result.evaluation_id,
            approved_at=now_utc(),
        )
        await self._materials.update(material)  # upsert by (summary, owner)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="daily_material.approved",
                payload={
                    "summary_id": str(summary.id),
                    "material_id": str(material.id),
                    "evaluation_id": material.evaluation_id,
                },
            )
        )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="daily_material.delivered",
                payload={"material_id": str(material.id)},
            )
        )
        report_info(
            "daily_material.delivered", "daily material delivered",
            summary_id=str(summary.id),
        )
        return material

    async def get_by_summary(
        self, owner_user_id: str, summary_id: str
    ) -> DailyMaterial | None:
        material = await self._materials.get_by_summary(summary_id, owner_user_id)
        if material is None or material.approved_at is None:
            # Unapproved material is NEVER returned (FR-042).
            return None
        return material

    async def require_by_summary(self, owner_user_id: str, summary_id: str) -> DailyMaterial:
        material = await self.get_by_summary(owner_user_id, summary_id)
        if material is None:
            raise NotFoundError(
                "material_not_found",
                "No approved material for this summary yet (FR-042).",
            )
        return material

    async def list_in_range(
        self, owner_user_id: str, from_instant, to_instant
    ) -> list[DailyMaterial]:
        materials = await self._materials.list_for_owner(
            owner_user_id, from_instant=from_instant, to_instant=to_instant
        )
        return [item for item in materials if item.approved_at is not None]

    async def count_materials(
        self, owner_user_id: str, from_instant, to_instant
    ) -> int:
        return len(await self.list_in_range(owner_user_id, from_instant, to_instant))