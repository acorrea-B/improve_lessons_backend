"""Feature availability + audit event + idempotency record entities
(US-13, FR-084, T030)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.base import Entity
from app.core.time.utc import AwareDatetime


class FeatureAvailability(Entity):
    # ``id`` doubles as the feature name in the collection
    # ``feature_availability_config`` (data-model.md): a string ``_id``.
    id: str
    enabled: bool
    updated_at: AwareDatetime
    updated_by: str

    model_config = ConfigDict(validate_assignment=True)


class AuditEvent(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str | None = None  # null for system events
    event_type: str
    payload: dict = Field(default_factory=dict)


class IdempotencyRecord(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    idempotency_key: str
    method: str
    path: str
    status_code: int
    response_body: str  # response body replayed verbatim
    expires_at: AwareDatetime