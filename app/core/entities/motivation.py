"""Motivation entities: recognitions and challenges (US-11).

These are computed/derived artifacts surfaced by the API; the data model
does not persist them as collections in this release — they are recorded
in ``audit_events`` payloads.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.base import Entity
from app.core.time.utc import AwareDatetime


class Recognition(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    kind: str  # e.g. "on_time_streak"
    description: str
    streak: int | None = None


class Challenge(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    kind: str = "daily"  # daily | weekly | monthly material
    target_cefr_level: str
    title: str
    description: str
    started: bool = False
    started_at: AwareDatetime | None = None