"""MongoDB adapter for the ``AssistantThreadRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.summary_chunk import AssistantThread


class AssistantThreadRepository(MongoRepository[AssistantThread]):
    entity_class = AssistantThread
    collection_name = "assistant_threads"
    _PORT = "AssistantThreadRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "AssistantThread | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[AssistantThread]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert(self, thread: "AssistantThread") -> "AssistantThread":
        return await super().insert(thread)

    async def list_for_owner(self, owner_user_id: str) -> "list[AssistantThread]":
        return await self.find_list(
            {"owner_user_id": owner_user_id}, sort=[("updated_at", -1)]
        )

    async def append_message(self, thread_id: str, owner_user_id: str, message: "ThreadMessage") -> "AssistantThread | None":
        from app.adapters.persistence.mongodb.mappers import normalize_value_write as normalize_value, load_entity
        result = await self.collection.find_one_and_update(
            {"_id": thread_id, "owner_user_id": owner_user_id},
            {
                "$push": {"messages": normalize_value("message", message.model_dump())},
                "$set": {"updated_at": normalize_value("updated_at", message.sent_at)},
            },
            return_document=__import__("pymongo").ReturnDocument.AFTER,
        )
        if result is None:
            return None
        return load_entity(self._entity_class, result)

    async def set_context_refs(
        self, thread_id: str, owner_user_id: str, context_refs: "list[str]"
    ) -> "AssistantThread | None":
        from app.adapters.persistence.mongodb.mappers import load_entity
        from pymongo import ReturnDocument

        result = await self.collection.find_one_and_update(
            {"_id": thread_id, "owner_user_id": owner_user_id},
            {"$set": {"retrieved_context_refs": context_refs}},
            return_document=ReturnDocument.AFTER,
        )
        return load_entity(self._entity_class, result) if result else None
