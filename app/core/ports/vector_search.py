"""VectorSearch"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.summary_chunk import SummaryChunk

from abc import ABC, abstractmethod


class VectorSearch(ABC):
    @abstractmethod
    async def index_chunks(self, chunks: "list[SummaryChunk]") -> None: ...

    @abstractmethod
    async def search(
        self,
        query_embedding: "list[float]",
        owner_user_id: str,
        *,
        top_k: int = 5,
    ) -> "list[SearchHit]":
        """Return the most relevant chunks, filtered by ``owner_user_id``."""
        ...


class SearchHit:
    def __init__(self, chunk_id: str, score: float, text: str, summary_id: str) -> None:
        self.chunk_id = chunk_id
        self.score = score
        self.text = text
        self.summary_id = summary_id

