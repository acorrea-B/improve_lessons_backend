"""Shared entity plumbing (data-model.md § Conventions).

Every entity is a pydantic model with:
- a UUID ``id`` (stored as the opaque ``_id`` in MongoDB),
- ``owner_user_id`` where the collection is user-scoped,
- UTC-aware timestamps serialized with the ``Z`` suffix via
  ``app.core.time.utc.AwareDatetime``.
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.time.utc import AwareDatetime, now_utc


class UUIDv4(BaseModel):
    # Annotation helper: validates default UUID generation.
    pass


class Entity(BaseModel):
    """Base for every domain entity."""

    model_config = ConfigDict(validate_assignment=True)

    id: UUID = Field(default_factory=uuid_module.uuid4)
    created_at: AwareDatetime = Field(default_factory=now_utc)

    def new_id(self) -> UUID:
        return uuid_module.uuid4()


def utc_now_field() -> datetime:
    """Explicit helper for subclasses building fields directly."""
    return now_utc()