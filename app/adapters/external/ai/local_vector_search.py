"""In-process vector search adapter (T020, research.md § 3).

Cosine similarity over numpy arrays for the ``summary_chunks`` persisted
through the ``SummaryChunkRepository``. Production uses MongoDB Atlas
``$vectorSearch`` behind the same ``VectorSearch`` port; the chunking,
embedding, retrieval and ranking code paths are identical for both.
"""

from __future__ import annotations

import numpy

from app.core.ports.summary_chunk_repository import SummaryChunkRepository
from app.core.ports.vector_search import SearchHit


class LocalVectorSearch:
    """Local-development / unit-test adapter for the vector search port."""

    def __init__(self, chunk_repository: SummaryChunkRepository) -> None:
        self._chunks = chunk_repository

    async def index_chunks(self, chunks) -> None:
        await self._chunks.insert_many(chunks)

    async def search(
        self,
        query_embedding: "list[float]",
        owner_user_id: str,
        *,
        top_k: int = 5,
    ) -> list[SearchHit]:
        chunks = await self._chunks.list_active_for_owner(owner_user_id)
        if not chunks:
            return []
        query = numpy.asarray(query_embedding, dtype=float)
        query_norm = float(numpy.linalg.norm(query)) or 1.0
        matrix = numpy.asarray([chunk.embedding for chunk in chunks], dtype=float)
        rows_norm = numpy.linalg.norm(matrix, axis=1)
        rows_norm[rows_norm == 0.0] = 1.0
        scores = (matrix @ query) / (rows_norm * query_norm)
        ranked = sorted(
            zip(chunks, scores.tolist()), key=lambda pair: pair[1], reverse=True
        )[:top_k]
        return [
            SearchHit(
                chunk_id=str(chunk.id),
                score=score,
                text=chunk.text,
                summary_id=str(chunk.summary_id),
            )
            for chunk, score in ranked
            if score > 0.0
        ]