"""MongoDB adapter for the ``PlatformRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.external_learning_platform import ExternalLearningPlatform


class PlatformRepository(MongoRepository[ExternalLearningPlatform]):
    entity_class = ExternalLearningPlatform
    collection_name = "external_learning_platforms"
    _PORT = "PlatformRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "ExternalLearningPlatform | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[ExternalLearningPlatform]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def delete(self, platform_id: str, owner_user_id: str) -> bool:
        return await self.delete_one_by_id(platform_id, owner_user_id)
