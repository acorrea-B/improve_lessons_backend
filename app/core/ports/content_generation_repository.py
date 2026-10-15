"""ContentGenerationRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.content_workflow import ContentGeneration

from abc import ABC, abstractmethod


class ContentGenerationRepository(ABC):
    @abstractmethod
    async def insert(self, generation: "ContentGeneration") -> "ContentGeneration": ...

    @abstractmethod
    async def get(self, generation_id: str, owner_user_id: str) -> "ContentGeneration | None": ...

