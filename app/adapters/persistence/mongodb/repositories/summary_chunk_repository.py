"""MongoDB adapter for the ``SummaryChunkRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.summary_chunk import SummaryChunk


class SummaryChunkRepository(MongoRepository[SummaryChunk]):
    entity_class = SummaryChunk
    collection_name = "summary_chunks"
    _PORT = "SummaryChunkRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "SummaryChunk | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[SummaryChunk]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert_many(self, chunks: "list[SummaryChunk]") -> "list[SummaryChunk]":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        documents = [dump_entity(chunk) for chunk in chunks]
        if documents:
            await self.collection.insert_many(documents)
        return chunks

    async def list_active_for_owner(self, owner_user_id: str) -> "list[SummaryChunk]":
        return await self.find_list(
            {"owner_user_id": owner_user_id, "is_obsolete": False}, limit=10000
        )

    async def supersede_chunks(self, owner_user_id: str, old_model_id: str, new_model_id: str) -> int:
        result = await self.collection.update_many(
            {
                "owner_user_id": owner_user_id,
                "embedding_model_id": old_model_id,
                "is_obsolete": False,
            },
            {"$set": {"is_obsolete": True}},
        )
        return result.modified_count
