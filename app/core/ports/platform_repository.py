"""PlatformRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.external_learning_platform import ExternalLearningPlatform

from abc import ABC, abstractmethod


class PlatformRepository(ABC):
    @abstractmethod
    async def insert(self, platform: "ExternalLearningPlatform") -> "ExternalLearningPlatform": ...

    @abstractmethod
    async def get(self, platform_id: str, owner_user_id: str) -> "ExternalLearningPlatform | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str) -> "list[ExternalLearningPlatform]": ...

    @abstractmethod
    async def delete(self, platform_id: str, owner_user_id: str) -> bool: ...

