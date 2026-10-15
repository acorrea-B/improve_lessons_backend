"""SummaryChunkRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.summary_chunk import SummaryChunk

from abc import ABC, abstractmethod


class SummaryChunkRepository(ABC):
    @abstractmethod
    async def insert_many(self, chunks: "list[SummaryChunk]") -> "list[SummaryChunk]": ...

    @abstractmethod
    async def list_active_for_owner(self, owner_user_id: str) -> "list[SummaryChunk]": ...

    @abstractmethod
    async def supersede_chunks(self, owner_user_id: str, old_model_id: str, new_model_id: str) -> int: ...

