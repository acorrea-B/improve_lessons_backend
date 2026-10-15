"""DailyMaterialRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.core.entities.materials import DailyMaterial

from abc import ABC, abstractmethod


class DailyMaterialRepository(ABC):
    @abstractmethod
    async def insert(self, material: "DailyMaterial") -> "DailyMaterial": ...

    @abstractmethod
    async def get(self, material_id: str, owner_user_id: str) -> "DailyMaterial | None": ...

    @abstractmethod
    async def get_by_summary(self, summary: str, owner_user_id: str) -> "DailyMaterial | None": ...

    @abstractmethod
    async def update(self, material: "DailyMaterial") -> "DailyMaterial": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[DailyMaterial]": ...

    @abstractmethod
    async def search_approved_by_user(self, owner_user_id: str, query: str, top_k: int) -> "list[DailyMaterial]":
        """Best-effort relevance lookup used when synthesizing rollups."""
        ...

