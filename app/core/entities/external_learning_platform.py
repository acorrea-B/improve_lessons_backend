"""External learning platform entity (data-model.md, US-2, FR-012)."""

from __future__ import annotations

from pydantic import Field

from app.core.entities.base import Entity


class ExternalLearningPlatform(Entity):
    owner_user_id: str
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)  # stored as provided (A-5)
    version: int = 1