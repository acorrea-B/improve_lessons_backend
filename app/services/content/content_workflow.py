"""Content workflow orchestration (T059, US-12).

Persists a ``content_generation`` row per attempt and a
``content_evaluation`` row per evaluation (with the right
``attempt_number``), emits the audit rows required by FR-086, and returns
the approved generation. Unapproved material is NEVER returned
(constitution principle II / X).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.entities.content_workflow import ContentEvaluation, ContentGeneration
from app.core.entities.feature_availability import AuditEvent
from app.core.errors import ServiceUnavailableError
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.content_evaluation_repository import ContentEvaluationRepository
from app.core.ports.content_generation_repository import ContentGenerationRepository
from app.utils.logging import get_logger, report_info

from app.services.content.corrective_loop import CorrectiveLoop

if TYPE_CHECKING:
    from app.core.entities.materials import GenerationInputs
    from app.core.ports.content_evaluator import EvaluationResult
    from app.core.ports.content_generator import GeneratedContent

logger = get_logger("services.content.workflow")


@dataclass
class WorkflowResult:
    approved: bool
    generation_id: str
    evaluation_id: str
    generation: "GeneratedContent | None" = None
    evaluation: "EvaluationResult | None" = None
    attempt_number: int = 0


class ContentWorkflowService:
    def __init__(
        self,
        loop: CorrectiveLoop,
        generations: ContentGenerationRepository,
        evaluations: ContentEvaluationRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self._loop = loop
        self._generations = generations
        self._evaluations = evaluations
        self._audit = audit_events

    async def produce(
        self,
        owner_user_id: str,
        purpose: str,
        inputs: "GenerationInputs",
    ) -> WorkflowResult:
        """Run the two-model workflow; return the APPROVED material only."""
        outcome = await self._loop.run(
            instruction=_instruction_for(purpose, inputs),
            inputs=inputs,
        )
        generations = outcome.attempts or ([outcome.generation] if outcome.generation else [])
        evaluations = outcome.evaluations or ([outcome.evaluation] if outcome.evaluation else [])

        persisted_generation_ids: list[str] = []
        for index, generation in enumerate(generations, start=1):
            generation_row = ContentGeneration(
                owner_user_id=owner_user_id,
                inputs=inputs.model_dump(),
                model_id=generation.model_id,
                raw_output=generation.raw_output,
            )
            await self._generations.insert(generation_row)
            persisted_generation_ids.append(str(generation_row.id))
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="content.generated",
                    payload={"generation_id": str(generation_row.id), "attempt": index},
                )
            )

        last_generation_id = persisted_generation_ids[-1] if persisted_generation_ids else ""
        for index, evaluation in enumerate(evaluations, start=1):
            # Evaluations map onto their corresponding generation; when the
            # transient-retry path reuses one generation the mapping stays
            # aligned with attempt order.
            generation_id = persisted_generation_ids[min(index - 1, len(persisted_generation_ids) - 1)] or last_generation_id
            evaluation_row = ContentEvaluation(
                owner_user_id=owner_user_id,
                generation_id=generation_id,
                model_id=evaluation.model_id,
                verdict=evaluation.verdict,
                criterion_assessments=evaluation.criterion_assessments,
                rationale=evaluation.rationale,
                attempt_number=evaluation_row_attempt(index),
            )
            await self._evaluations.insert(evaluation_row)
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="content.evaluated",
                    payload={
                        "evaluation_id": str(evaluation_row.id),
                        "generation_id": generation_id,
                        "verdict": evaluation.verdict.value,
                        "attempt_number": index,
                        "criterion_assessments": [
                            {"criterion": item.criterion, "passed": item.passed}
                            for item in evaluation.criterion_assessments
                        ],
                    },
                )
            )

        last_evaluation = evaluations[-1] if evaluations else None
        final_evaluation_id = ""
        if last_evaluation is not None:
            # The approved/linked evaluation id is the row persisted for the
            # final attempt.
            rows = await self._evaluations.list_by_generation(
                last_generation_id, owner_user_id
            )
            final_evaluation_id = str(rows[-1].id) if rows else ""

        if outcome.approved:
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=owner_user_id,
                    event_type="content.approved",
                    payload={
                        "generation_id": last_generation_id,
                        "evaluation_id": final_evaluation_id,
                    },
                )
            )
            report_info(
                "content.approved", "material approved",
                attempt_number=outcome.attempt_number,
            )
            return WorkflowResult(
                approved=True,
                generation_id=last_generation_id,
                evaluation_id=final_evaluation_id,
                generation=outcome.generation,
                evaluation=outcome.evaluation,
                attempt_number=outcome.attempt_number,
            )

        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="content.bound_exhausted"
                if outcome.status == "bound_exhausted"
                else "content.rejected",
                payload={"attempt_number": outcome.attempt_number},
            )
        )
        # Contained failure: a clear error, no unapproved material returned.
        raise ServiceUnavailableError(
            "content_workflow_failed",
            "The content workflow could not produce approved material; "
            "please retry later.",
        )


def evaluation_row_attempt(index: int) -> int:
    return index


def _instruction_for(purpose: str, inputs: "GenerationInputs") -> str:
    history = "\n".join(f"- {item}" for item in inputs.history_slice) or "- (no history yet)"
    return (
        f"Purpose: {purpose}\n"
        f"Target CEFR level: {inputs.cefr_level}\n"
        f"Documented learning history:\n{history}\n"
        f"Period objective: {inputs.period_objective or 'steady practice'}\n"
        "Produce a reading passage and writing exercises strictly at the "
        "target level, grounded in the documented history."
    )