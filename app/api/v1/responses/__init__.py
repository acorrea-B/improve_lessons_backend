"""API response helpers (T023).

Entities are pydantic models whose instants use ``AwareDatetime`` with the
global ``Z``-suffix serializer, so ``model_dump(mode="json")`` always emits
``2026-10-13T14:30:00Z`` and never ``+00:00``. The helpers below produce
snake-cased stable response shapes (contract § Sample shapes).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.time.utc import now_utc


def serialize(entity: BaseModel | Any) -> dict[str, Any]:
    """Entity → JSON-ready dict (UUIDs → strings, instants → ``Z``)."""
    if hasattr(entity, "model_dump"):
        return entity.model_dump(mode="json")
    return entity


def serialize_list(entities) -> list[dict[str, Any]]:
    return [serialize(entity) for entity in entities]


def error_envelope(code: str, message: str, details=None) -> dict:
    envelope: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        envelope["error"]["details"] = details
    return envelope