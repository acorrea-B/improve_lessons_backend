"""MongoDB adapter for the ``MonthlyMaterialRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.materials import MonthlyMaterial


class MonthlyMaterialRepository(MongoRepository[MonthlyMaterial]):
    entity_class = MonthlyMaterial
    collection_name = "monthly_materials"
    _PORT = "MonthlyMaterialRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "MonthlyMaterial | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[MonthlyMaterial]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def get_by_monthly_summary(self, monthly_summary_id: str, owner_user_id: str) -> "MonthlyMaterial | None":
        return await self.find_one({"monthly_summary_id": monthly_summary_id, "owner_user_id": owner_user_id})

    async def update(self, material: "MonthlyMaterial") -> "MonthlyMaterial":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(material)
        await self.collection.replace_one(
            {"_id": document["_id"], "owner_user_id": material.owner_user_id},
            document,
            upsert=True,
        )
        return material

    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[MonthlyMaterial]":
        return await self.find_list({"owner_user_id": owner_user_id}, sort=[("created_at", 1)], limit=1000)

    async def search_approved_by_user(self, owner_user_id: str, query: str, top_k: int) -> "list[MonthlyMaterial]":
        return []
