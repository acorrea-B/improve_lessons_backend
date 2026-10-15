"""RAG pipeline (T087, US-9, research.md § 4).

persist summary → chunk → embed → index chunks in ``summary_chunks``.
Retrieval filters by ``owner_user_id`` for per-user isolation (constitution
principle III). The chunking/embedding strategy is the deferred-decision
placeholder: sentence-aware chunking with a bounded character budget.

The vector representation NEVER replaces the original summary (plan §3.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.entities.summary_chunk import SummaryChunk
from app.core.ports.embedding_provider import EmbeddingProvider
from app.core.ports.vector_search import VectorSearch
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    from app.core.entities.daily_summary import DailySummary

#: Deferred-decision placeholder: sentence-aware chunking with a bounded
#: character budget and no overlap (documented as the pending open decision).
CHUNK_MAX_CHARS = 480
_CHUNK_SEPARATORS = (". ", "! ", "? ", "\n")


def chunk_text(text: str, *, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Sentence-aware chunking within ``max_chars`` (no overlap)."""
    text = text.strip()
    if not text:
        return []
    sentences: list[str] = []
    current = ""
    for token in _split_sentences(text):
        if current and len(current) + len(token) > max_chars:
            sentences.append(current.strip())
            current = ""
        current += token
        if len(current) >= max_chars:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    buffer = ""
    for character in text:
        buffer += character
        if any(buffer.endswith(sep) for sep in _CHUNK_SEPARATORS):
            parts.append(buffer)
            buffer = ""
    if buffer:
        parts.append(buffer)
    return parts


def count_tokens(text: str) -> int:
    """Token budget approximation (≈ words + punctuation)."""
    return max(1, len(text.split()))


class RAGService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_search: VectorSearch,
    ) -> None:
        self._embeddings = embedding_provider
        self._vector_search = vector_search

    async def ingest(self, summary: "DailySummary") -> list[SummaryChunk]:
        """Chunk, embed and index the (append-only) summary."""
        chunks = chunk_text(summary.content)
        if not chunks:
            return []
        embeddings = await self._embeddings.embed(chunks)
        records = [
            SummaryChunk(
                owner_user_id=summary.owner_user_id,
                summary_id=str(summary.id),
                summary_content_version=summary.content_version,
                chunk_index=index,
                text=text,
                token_count=count_tokens(text),
                embedding_model_id=self._embeddings.model_id,
                embedding=embedding,
                embedding_dim=self._embeddings.embedding_dim,
            )
            for index, (text, embedding) in enumerate(zip(chunks, embeddings))
        ]
        await self._vector_search.index_chunks(records)
        report_info(
            "rag.indexed", "summary chunks indexed",
            summary_id=str(summary.id), chunks=len(records),
        )
        return records

    async def retrieve(
        self, owner_user_id: str, query: str, *, top_k: int = 5
    ) -> tuple[list[str], list[str]]:
        """Return (context_texts, chunk_ids) — owner-filtered (per-user
        isolation enforced at the vector adapter)."""
        embedding = (await self._embeddings.embed([query]))[0]
        hits = await self._vector_search.search(embedding, owner_user_id, top_k=top_k)
        return [hit.text for hit in hits], [hit.chunk_id for hit in hits]