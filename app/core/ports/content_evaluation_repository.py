"""ContentEvaluationRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.content_workflow import ContentEvaluation

from abc import ABC, abstractmethod


class ContentEvaluationRepository(ABC):
    @abstractmethod
    async def insert(self, evaluation: "ContentEvaluation") -> "ContentEvaluation": ...

    @abstractmethod
    async def get(self, evaluation_id: str, owner_user_id: str) -> "ContentEvaluation | None": ...

    @abstractmethod
    async def list_by_generation(self, generation_id: str, owner_user_id: str) -> "list[ContentEvaluation]": ...

    @abstractmethod
    async def count_by_generation(self, generation_id: str, owner_user_id: str) -> int: ...

