"""MongoDB adapter for the ``ContentEvaluationRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.content_workflow import ContentEvaluation


class ContentEvaluationRepository(MongoRepository[ContentEvaluation]):
    entity_class = ContentEvaluation
    collection_name = "content_evaluations"
    _PORT = "ContentEvaluationRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "ContentEvaluation | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[ContentEvaluation]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert(self, evaluation: "ContentEvaluation") -> "ContentEvaluation":
        return await super().insert(evaluation)

    async def list_by_generation(self, generation_id: str, owner_user_id: str) -> "list[ContentEvaluation]":
        return await self.find_list(
            {"generation_id": generation_id, "owner_user_id": owner_user_id},
            sort=[("attempt_number", 1)],
        )

    async def count_by_generation(self, generation_id: str, owner_user_id: str) -> int:
        return await self.collection.count_documents(
            {"generation_id": generation_id, "owner_user_id": owner_user_id}
        )
