"""Schedule entity (data-model.md § schedules, US-2).

``start_time`` / ``end_time`` are LOCAL wall-clock ``HH:MM`` strings
evaluated in the user's time zone — they are NOT instants and are never
converted in isolation (plan.md § Mandatory Standards, rule 2).
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator, model_validator

from app.core.entities.base import Entity
from app.core.entities.enums import Modality, Recurrence
from app.core.errors import ValidationErrorDetail
from app.core.time.utc import AwareDatetime

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _validate_hhmm(value: str, field: str) -> str:
    if not _HHMM.match(value):
        raise ValidationErrorDetail(
            code="invalid_HHMM",
            message=f"{field} must be a local wall-clock HH:MM string.",
            details={"field": field, "value": value},
        )
    return value


class Schedule(Entity):
    owner_user_id: str
    start_time: str  # local HH:MM in the user's tz
    end_time: str  # local HH:MM, strictly after start_time (FR-010)
    recurrence: Recurrence
    modality: Modality
    # Exactly one of platform_id / location is set per the modality.
    platform_id: str | None = None
    platform_url: str | None = None  # denormalized snapshot for reminders
    location: str | None = None
    updated_at: AwareDatetime
    version: int = 1

    @field_validator("start_time", "end_time")
    @classmethod
    def _hhmm(cls, value: str, info) -> str:
        return _validate_hhmm(value, info.field_name)

    @model_validator(mode="after")
    def _modality_consistency(self) -> "Schedule":
        if self.modality is Modality.VIRTUAL:
            if self.platform_id is None or self.location is not None:
                raise ValidationErrorDetail(
                    code="invalid_schedule",
                    message="A virtual schedule must reference a platform.",
                    details={"field": "platform_id"},
                )
        else:
            if self.platform_id is not None or self.location is None:
                raise ValidationErrorDetail(
                    code="invalid_schedule",
                    message="An in-person schedule must carry a location.",
                    details={"field": "location"},
                )
        # FR-010: end_time must be strictly after start_time (lexical
        # comparison — both are same-day local wall-clock HH:MM values).
        if self.end_time <= self.start_time:
            raise ValidationErrorDetail(
                code="invalid_time_range",
                message="end_time must be strictly after start_time (FR-010).",
                details={"field": "end_time"},
            )
        return self