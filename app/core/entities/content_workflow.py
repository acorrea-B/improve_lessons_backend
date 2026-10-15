"""Content workflow entities (US-12, data-model.md § content_generations /
content_evaluations)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.base import Entity
from app.core.entities.enums import Verdict
from app.core.time.utc import AwareDatetime


class ContentGeneration(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    inputs: dict  # CEFR level, purpose, history slice, period objective
    model_id: str
    raw_output: str


class CriterionAssessment(BaseModel):
    """Structured per-criterion assessment (constitution principle II)."""

    criterion: str
    passed: bool
    comment: str = ""

    model_config = ConfigDict(extra="forbid")


class ContentEvaluation(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    generation_id: str
    model_id: str
    verdict: Verdict
    criterion_assessments: list[CriterionAssessment] = Field(min_length=1)
    rationale: str
    attempt_number: int  # 1-based; increments across the corrective loop