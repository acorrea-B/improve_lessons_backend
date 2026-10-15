"""SummaryRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.daily_summary import DailySummary

from abc import ABC, abstractmethod


class SummaryRepository(ABC):
    @abstractmethod
    async def insert(self, summary: "DailySummary") -> "DailySummary":
        """Insert-only: raises on a duplicate ``session_id`` (FR-024a)."""
        ...

    @abstractmethod
    async def get(self, summary_id: str, owner_user_id: str) -> "DailySummary | None": ...

    @abstractmethod
    async def get_by_session(self, session_id: str, owner_user_id: str) -> "DailySummary | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[DailySummary]": ...

