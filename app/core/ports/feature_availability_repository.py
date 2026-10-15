"""FeatureAvailabilityRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.feature_availability import FeatureAvailability

from abc import ABC, abstractmethod


class FeatureAvailabilityRepository(ABC):
    @abstractmethod
    async def get(self, feature: str) -> "FeatureAvailability | None": ...

    @abstractmethod
    async def set(self, availability: "FeatureAvailability") -> "FeatureAvailability": ...

    @abstractmethod
    async def list_all(self) -> "list[FeatureAvailability]": ...

