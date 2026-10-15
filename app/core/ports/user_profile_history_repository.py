"""UserProfileHistoryRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.user import ProfileChange

from abc import ABC, abstractmethod


class UserProfileHistoryRepository(ABC):
    @abstractmethod
    async def append(self, change: "ProfileChange") -> "ProfileChange":
        """Append one row; the collection is append-only."""
        ...

    @abstractmethod
    async def list_for_user(self, user_id: str) -> "list[ProfileChange]": ...

