"""Bidirectional mappers between domain entities and MongoDB documents
(T018).

- WRITE direction: a naive datetime raises ``NaiveDatetimeError`` before
  any insert/update (data-model.md § Time-zone handling).
- READ direction: BSON ``Date`` decodes as a *naive* datetime that is UTC
  by definition; the mapper attaches ``UTC`` so every entity carries
  aware UTC instants (quickstart § 9.2 persistence invariant).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.core.errors import DomainError
from app.core.time.utc import require_aware_utc
from app.core.time.utc import UTC as _UTC


class NaiveDatetimeError(DomainError):
    def __init__(self, field: str) -> None:
        super().__init__(
            "naive_datetime_rejected",
            f"Field '{field}' is a naive datetime; UTC invariant violated.",
            details={"field": field},
        )
        self.field = field


EntityT = TypeVar("EntityT", bound=BaseModel)


def normalize_value_write(field: str, value: Any) -> Any:
    """Write direction: UUID → str, aware datetime → UTC, recursive."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise NaiveDatetimeError(field)
        return value.astimezone(UTC)
    if isinstance(value, dict):
        return {
            key: normalize_value_write(f"{field}.{key}", item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_value_write(field, item) for item in value]
    if isinstance(value, BaseModel):
        return normalize_value_write(field, value.model_dump())
    return value


def normalize_value_read(field: str, value: Any) -> Any:
    """Read direction: BSON Date (naive, UTC by definition) → aware UTC."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, dict):
        return {
            key: normalize_value_read(f"{field}.{key}", item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_value_read(field, item) for item in value]
    if isinstance(value, BaseModel):
        return normalize_value_read(field, value.model_dump())
    return value


def dump_entity(entity: BaseModel) -> dict[str, Any]:
    """Entity → MongoDB document (``id`` becomes ``_id``, UUIDs → strings)."""
    values = entity.model_dump(exclude={"id"})
    document: dict[str, Any] = {}
    for key, value in values.items():
        document[key] = normalize_value_write(key, value)
    document["_id"] = str(entity.id)  # type: ignore[attr-defined]
    return document


def load_entity(entity_class: type[EntityT], document: dict[str, Any]) -> EntityT:
    """MongoDB document → entity (aware UTC instants everywhere)."""
    loaded = dict(document)
    entity_id = loaded.pop("_id", None)
    if entity_id is not None:
        loaded["id"] = entity_id
    loaded = normalize_value_read("$document", loaded)
    return entity_class.model_validate(loaded)


def require_utc_document_datetime(document: dict[str, Any], field: str) -> datetime:
    """Read a persisted instant and prove it round-trips as aware UTC
    (quickstart.md § 9.2 invariant helper)."""
    value = document.get(field)
    if value is None:
        raise NaiveDatetimeError(field)
    return require_aware_utc(value, argument=field)


class DomainMapper:
    """Per-entity mapper wrapper (traceable to data-model.md)."""

    def __init__(self, entity_class: type) -> None:
        self._entity_class = entity_class

    def to_document(self, entity) -> dict[str, Any]:
        return dump_entity(entity)

    def to_entity(self, document: dict[str, Any]):
        return load_entity(self._entity_class, document)


def dump_id(value: UUID | str) -> str:
    return value if isinstance(value, str) else str(value)