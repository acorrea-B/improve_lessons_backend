"""EmbeddingProvider"""
from __future__ import annotations


from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    model_id: str
    embedding_dim: int

    @abstractmethod
    async def embed(self, texts: "list[str]") -> "list[list[float]]": ...

