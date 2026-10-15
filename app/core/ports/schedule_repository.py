"""ScheduleRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.schedule import Schedule

from abc import ABC, abstractmethod


class ScheduleRepository(ABC):
    @abstractmethod
    async def insert(self, schedule: "Schedule") -> "Schedule": ...

    @abstractmethod
    async def get(self, schedule_id: str, owner_user_id: str) -> "Schedule | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str) -> "list[Schedule]": ...

    @abstractmethod
    async def update(self, schedule: "Schedule") -> "Schedule": ...

    @abstractmethod
    async def delete(self, schedule_id: str, owner_user_id: str) -> bool: ...

