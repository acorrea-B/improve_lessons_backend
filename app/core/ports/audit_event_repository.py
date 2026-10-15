"""AuditEventRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.feature_availability import AuditEvent

from abc import ABC, abstractmethod


class AuditEventRepository(ABC):
    @abstractmethod
    async def insert(self, event: "AuditEvent") -> "AuditEvent":
        """Append-only structured audit write (FR-084-086)."""
        ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, limit: int = 100) -> "list[AuditEvent]": ...

