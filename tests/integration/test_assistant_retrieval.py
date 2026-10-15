"""US-9 RAG retrieval integration tests (T085/T087): chunks are indexed on
summary insert, retrieval is relevance-filtered, and per-user isolation
holds (a second user's chunks never leak)."""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.ai.deterministic_ai import (
    DeterministicEmbeddingProvider,
)
from app.adapters.external.ai.local_vector_search import LocalVectorSearch
from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import SummaryChunkRepository
from app.core.entities.daily_summary import DailySummary
from app.core.entities.enums import SubmissionStatus
from app.core.time.utc import now_utc
from app.services.rag_service import RAGService, chunk_text

from tests.commons.fixtures import mongo_available, mongo_isolated_database


async def build_rag(mongo):
    chunks = SummaryChunkRepository(mongo)
    provider = DeterministicEmbeddingProvider()
    return RAGService(provider, LocalVectorSearch(chunks)), chunks


async def store_summary(chunk_repo, rag, owner: str, content: str):
    summary = DailySummary(
        owner_user_id=owner,
        session_id=f"session-{owner}-{abs(hash(content)) % 100000}",
        content=content,
        submitted_at=now_utc(),
        submission_status=SubmissionStatus.ON_TIME,
        submitted_before_session_start=False,
    )
    await rag.ingest(summary)
    return summary


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestRAGPipeline(unittest.TestCase):
    def test_chunking_is_sentence_aware(self):
        text = "First sentence about adverbs. Second sentence covering grammar. Third one about reading."
        chunks = chunk_text(text, max_chars=80)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk) <= 160 for chunk in chunks))
        self.assertEqual("".join(c.strip() for c in chunks).replace(" ", ""), text.replace(" ", ""), "chunks keep the text content")

    def test_retrieval_ranks_relevant_history_highest(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    rag, _chunks = await build_rag(mongo)
                    await store_summary(
                        None, rag, "user-rag-1",
                        "I studied adverbs of frequency and the present simple today.",
                    )
                    await store_summary(
                        None, rag, "user-rag-1",
                        "I cooked dinner and talked about football with friends.",
                    )
                    texts, ids = await rag.retrieve("user-rag-1", "adverbs of frequency")
                    self.assertTrue(texts)
                    self.assertIn("adverbs of frequency", texts[0])
                finally:
                    await mongo.close()

        run(scenario())

    def test_per_user_isolation(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    rag, chunks = await build_rag(mongo)
                    await store_summary(
                        chunks, rag, "user-rag-a",
                        "Private A: phrasal verbs and register.",
                    )
                    await store_summary(
                        chunks, rag, "user-rag-b",
                        "Private B: kitchen vocabulary and recipes.",
                    )
                    texts, ids = await rag.retrieve("user-rag-a", "phrasal verbs")
                    for text in texts:
                        self.assertNotIn("recipes", text)
                    texts_b, _ids = await rag.retrieve("user-rag-b", "phrasal verbs")
                    for text in texts_b:
                        self.assertNotIn("register", text)
                finally:
                    await mongo.close()

        run(scenario())


if __name__ == "__main__":
    unittest.main()