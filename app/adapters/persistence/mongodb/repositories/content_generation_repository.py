"""MongoDB adapter for the ``ContentGenerationRepository`` port (T019)."""

from __future__ import annotations

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories.base import MongoRepository
from app.core.entities.content_workflow import ContentGeneration


class ContentGenerationRepository(MongoRepository[ContentGeneration]):
    entity_class = ContentGeneration
    collection_name = "content_generations"
    _PORT = "ContentGenerationRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "ContentGeneration | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[ContentGeneration]":
        return await self.find_list({"owner_user_id": owner_user_id})
