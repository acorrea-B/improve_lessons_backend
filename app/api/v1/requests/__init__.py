"""API request models (T022).

Every field that represents an instant uses ``AwareDatetime`` (bound to
UTC: naive values are rejected with ``error.code = invalid_timestamp`` and
explicit offsets are normalized to UTC). Local wall-clock fields
(``start_time`` / ``end_time``) are ``HH:MM`` strings and not instants.

T109/T110: the shared fixtures in ``scripts/smoke_test.sh`` exercise the
same rules via the API.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.api.v1.requests.wall_clock import HHMMString
from app.core.time.utc import AwareDatetime

__all__ = [
    "AwareDatetime",
    "HHMMString",
    "LoginRequest",
    "MessageRequest",
    "PlatformCreateRequest",
    "RegisterRequest",
    "ScheduleCreateRequest",
    "ScheduleUpdateRequest",
    "SummaryCreateRequest",
    "UpdateProfileRequest",
    "TimestampProbeRequest",
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    email: EmailStr
    cefr_level: str
    time_zone: str
    password: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str | None = None


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    preferred_name: str | None = None
    email: EmailStr | None = None
    cefr_level: str | None = None
    time_zone: str | None = None


class PlatformCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    url: str = Field(min_length=1)


class ScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Local wall-clock HH:MM strings in the user's tz — NOT instants.
    start_time: HHMMString
    end_time: HHMMString
    recurrence: str
    modality: str
    platform_id: str | None = None
    location: str | None = None


class ScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: HHMMString | None = None
    end_time: HHMMString | None = None
    recurrence: str | None = None
    modality: str | None = None
    platform_id: str | None = None
    location: str | None = None


class SummaryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str


class TimestampProbeRequest(BaseModel):
    """Accepts an optional instant to exercise the UTC contract rules
    (quickstart.md § 9.1 fixtures)."""

    model_config = ConfigDict(extra="forbid")

    submitted_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _noop(self) -> "TimestampProbeRequest":
        return self