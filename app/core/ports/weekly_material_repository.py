"""WeeklyMaterialRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.materials import WeeklyMaterial

from abc import ABC, abstractmethod


class WeeklyMaterialRepository(ABC):
    @abstractmethod
    async def insert(self, material: "WeeklyMaterial") -> "WeeklyMaterial": ...

    @abstractmethod
    async def get(self, material_id: str, owner_user_id: str) -> "WeeklyMaterial | None": ...

    @abstractmethod
    async def get_by_weekly_summary(self, weekly_summary: str, owner_user_id: str) -> "WeeklyMaterial | None": ...

    @abstractmethod
    async def update(self, material: "WeeklyMaterial") -> "WeeklyMaterial": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[WeeklyMaterial]": ...

    @abstractmethod
    async def search_approved_by_user(self, owner_user_id: str, query: str, top_k: int) -> "list[WeeklyMaterial]":
        """Best-effort relevance lookup used when synthesizing rollups."""
        ...

