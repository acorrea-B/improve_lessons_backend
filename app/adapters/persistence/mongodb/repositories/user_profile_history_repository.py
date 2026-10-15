"""MongoDB adapter for the ``UserProfileHistoryRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.user import ProfileChange


class UserProfileHistoryRepository(MongoRepository[ProfileChange]):
    entity_class = ProfileChange
    collection_name = "users_profile_history"
    _PORT = "UserProfileHistoryRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "ProfileChange | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[ProfileChange]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def append(self, change: "ProfileChange") -> "ProfileChange":
        return await self.insert(change)

    async def list_for_user(self, user_id: str) -> "list[ProfileChange]":
        return await self.find_list({"user_id": user_id}, sort=[("changed_at", 1)])
