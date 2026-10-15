"""SessionRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.session import Session

from abc import ABC, abstractmethod


class SessionRepository(ABC):
    @abstractmethod
    async def insert_many(self, sessions: "list[Session]") -> "list[Session]":
        """Insert sessions; skip duplicates for the same schedule+start."""
        ...

    @abstractmethod
    async def get(self, session_id: str, owner_user_id: str) -> "Session | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[Session]": ...

    @abstractmethod
    async def list_pending_reminders(self, window_start, window_end) -> "list[Session]": ...

    @abstractmethod
    async def update(self, session: "Session") -> "Session": ...

    @abstractmethod
    async def delete_future_for_schedule(self, schedule_id: str, now) -> int: ...

