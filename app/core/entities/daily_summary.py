"""Daily summary entity — append-only learning record (US-4, FR-024/024a)."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from app.core.entities.base import Entity
from app.core.entities.enums import SubmissionStatus
from app.core.time.utc import AwareDatetime


class DailySummary(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    session_id: str  # unique per session, enforced by the database
    content: str = Field(min_length=1)
    content_version: int = 1  # never updated in this release
    submitted_at: AwareDatetime
    submission_status: SubmissionStatus  # computed at insert time, immutable
    submitted_before_session_start: bool
    reminder_id: str | None = None