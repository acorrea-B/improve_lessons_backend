"""ContentEvaluator"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.content_workflow import CriterionAssessment
    from app.core.entities.enums import Verdict
    from app.core.ports.content_generator import GeneratedContent


class EvaluationResult:
    """Structured result of a Content Evaluation Model run."""

    def __init__(
        self,
        model_id: str,
        verdict: "Verdict",
        criterion_assessments: "list[CriterionAssessment]",
        rationale: str,
    ) -> None:
        self.model_id = model_id
        self.verdict = verdict
        self.criterion_assessments = criterion_assessments
        self.rationale = rationale

from abc import ABC, abstractmethod


class ContentEvaluator(ABC):
    model_id: str

    @abstractmethod
    async def evaluate(
        self,
        generated: "GeneratedContent",
        cefr_level: str,
        purpose: str,
    ) -> "EvaluationResult":
        """Assess generated material against the six CEFR criteria."""
        ...

