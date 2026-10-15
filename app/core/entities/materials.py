"""Material entities — daily/weekly/monthly reading & writing exercises.

All three share the same shape and approval rules (data-model.md): a
material carries exactly one ``generation_id`` and one ``evaluation_id``,
and is only delivered when the linked evaluation is ``approved`` (FR-042).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.base import Entity
from app.core.time.utc import AwareDatetime


class ReadingContent(BaseModel):
    title: str
    body: str
    vocabulary: list[str] = Field(default_factory=list)


class WritingExercise(BaseModel):
    prompt: str

    model_config = ConfigDict(extra="forbid")


class GenerationInputs(BaseModel):
    """Structured inputs recorded on every content_generation row."""

    cefr_level: str
    purpose: str
    history_slice: list[str] = Field(default_factory=list)
    period_objective: str | None = None


class DailyMaterial(Entity):
    owner_user_id: str
    summary_id: str  # unique per summary
    reading: ReadingContent
    writing_exercises: list[WritingExercise] = Field(min_length=1)
    generation_id: str
    evaluation_id: str
    approved_at: AwareDatetime | None = None
    content_version: int = 1


class WeeklySummary(Entity):
    owner_user_id: str
    week_start_at: AwareDatetime  # Monday 00:00 in the user's tz, stored UTC
    week_end_at: AwareDatetime  # next Monday 00:00 in the user's tz
    on_time_count: int = 0
    late_count: int = 0
    missing_count: int = 0
    recorded_study_minutes: int = 0
    consistency_indicators: dict = Field(default_factory=dict)
    knowledge_synthesis: str = ""
    weekly_material_id: str | None = None


class WeeklyMaterial(Entity):
    owner_user_id: str
    weekly_summary_id: str  # unique
    reading: ReadingContent
    writing_exercises: list[WritingExercise] = Field(min_length=1)
    generation_id: str
    evaluation_id: str
    approved_at: AwareDatetime | None = None
    content_version: int = 1


class MonthlySummary(Entity):
    owner_user_id: str
    month_start_at: AwareDatetime  # 1st of month 00:00 in the user's tz, UTC
    month_end_at: AwareDatetime
    on_time_count: int = 0
    late_count: int = 0
    missing_count: int = 0
    recorded_study_minutes: int = 0
    consistency_indicators: dict = Field(default_factory=dict)
    knowledge_synthesis: str = ""
    monthly_material_id: str | None = None


class MonthlyMaterial(Entity):
    owner_user_id: str
    monthly_summary_id: str  # unique
    reading: ReadingContent
    writing_exercises: list[WritingExercise] = Field(min_length=1)
    generation_id: str
    evaluation_id: str
    approved_at: AwareDatetime | None = None
    content_version: int = 1