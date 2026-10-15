"""WeeklySummaryRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.materials import WeeklySummary

from abc import ABC, abstractmethod


class WeeklySummaryRepository(ABC):
    @abstractmethod
    async def insert(self, summary: "WeeklySummary") -> "WeeklySummary": ...

    @abstractmethod
    async def get(self, summary_id: str, owner_user_id: str) -> "WeeklySummary | None": ...

    @abstractmethod
    async def get_by_period(self, owner_user_id: str, week_start_at) -> "WeeklySummary | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[WeeklySummary]": ...

    @abstractmethod
    async def update(self, summary: "WeeklySummary") -> "WeeklySummary": ...

