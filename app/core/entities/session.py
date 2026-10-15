"""Session entity — a concrete planned learning event (data-model.md)."""

from __future__ import annotations

from pydantic import ConfigDict, model_validator

from app.core.entities.base import Entity
from app.core.entities.enums import Modality
from app.core.errors import ValidationErrorDetail
from app.core.time.utc import AwareDatetime


class Session(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    schedule_id: str
    scheduled_start_at: AwareDatetime
    scheduled_end_at: AwareDatetime
    modality: Modality
    platform_id: str | None = None
    platform_url: str | None = None
    location: str | None = None
    reminder_sent_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _end_after_start(self) -> "Session":
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise ValidationErrorDetail(
                code="invalid_session_interval",
                message="scheduled_end_at must be strictly after scheduled_start_at.",
            )
        return self