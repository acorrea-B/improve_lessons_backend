"""User domain entity (data-model.md § users, US-1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.entities.base import Entity
from app.core.entities.enums import CEFRLevel
from app.core.time.utc import AwareDatetime


class User(Entity):
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(min_length=1)
    preferred_name: str | None = None
    email: EmailStr  # RFC-5322 validation; stored lowercased by the service
    cefr_level: CEFRLevel
    time_zone: str  # IANA tz identifier; validated by zoneinfo in the service
    # Authentication placeholder (research.md § 7: mechanism deferred). A
    # registered user may set no password; login then matches email only.
    password_hash: str | None = None
    # Invalidates tokens issued before this instant (set on logout).
    session_valid_after: AwareDatetime | None = None
    updated_at: AwareDatetime
    version: int = 1


class ProfileChange(Entity):
    """One append-only row of ``users_profile_history``."""

    model_config = ConfigDict(validate_assignment=True)

    user_id: str  # UUID as string
    changed_fields: dict[str, dict[str, str | None]]
    changed_at: AwareDatetime
    version: int = 1