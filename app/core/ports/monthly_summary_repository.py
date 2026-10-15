"""MonthlySummaryRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.materials import MonthlySummary

from abc import ABC, abstractmethod


class MonthlySummaryRepository(ABC):
    @abstractmethod
    async def insert(self, summary: "MonthlySummary") -> "MonthlySummary": ...

    @abstractmethod
    async def get(self, summary_id: str, owner_user_id: str) -> "MonthlySummary | None": ...

    @abstractmethod
    async def get_by_period(self, owner_user_id: str, month_start_at) -> "MonthlySummary | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[MonthlySummary]": ...

