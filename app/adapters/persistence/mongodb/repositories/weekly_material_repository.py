"""MongoDB adapter for the ``WeeklyMaterialRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.materials import WeeklyMaterial


class WeeklyMaterialRepository(MongoRepository[WeeklyMaterial]):
    entity_class = WeeklyMaterial
    collection_name = "weekly_materials"
    _PORT = "WeeklyMaterialRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "WeeklyMaterial | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[WeeklyMaterial]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def get_by_weekly_summary(self, weekly_summary_id: str, owner_user_id: str) -> "WeeklyMaterial | None":
        return await self.find_one({"weekly_summary_id": weekly_summary_id, "owner_user_id": owner_user_id})

    async def update(self, material: "WeeklyMaterial") -> "WeeklyMaterial":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(material)
        await self.collection.replace_one(
            {"_id": document["_id"], "owner_user_id": material.owner_user_id},
            document,
            upsert=True,
        )
        return material

    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[WeeklyMaterial]":
        query: dict = {"owner_user_id": owner_user_id}
        return await self.find_list(query, sort=[("created_at", 1)], limit=1000)

    async def search_approved_by_user(self, owner_user_id: str, query: str, top_k: int) -> "list[WeeklyMaterial]":
        return []
