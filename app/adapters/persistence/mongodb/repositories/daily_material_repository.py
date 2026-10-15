"""MongoDB adapter for the ``DailyMaterialRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.materials import DailyMaterial


class DailyMaterialRepository(MongoRepository[DailyMaterial]):
    entity_class = DailyMaterial
    collection_name = "daily_materials"
    _PORT = "DailyMaterialRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "DailyMaterial | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[DailyMaterial]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def get_by_summary(self, summary_id: str, owner_user_id: str) -> "DailyMaterial | None":
        return await self.find_one({"summary_id": summary_id, "owner_user_id": owner_user_id})

    async def update(self, material: "DailyMaterial") -> "DailyMaterial":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(material)
        result = await self.collection.replace_one(
            {"_id": document["_id"], "owner_user_id": material.owner_user_id},
            document,
            upsert=True,
        )
        return material

    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[DailyMaterial]":
        query: dict = {"owner_user_id": owner_user_id}
        if from_instant is not None or to_instant is not None:
            range_filter: dict = {}
            if from_instant is not None:
                range_filter["$gte"] = from_instant
            if to_instant is not None:
                range_filter["$lt"] = to_instant
            query["created_at"] = range_filter
        return await self.find_list(query, sort=[("created_at", 1)], limit=5000)

    async def search_approved_by_user(self, owner_user_id: str, query: str, top_k: int) -> "list[DailyMaterial]":
        """Substring-based best-effort relevance over approved materials."""
        documents = await self.collection.find(
            {
                "owner_user_id": owner_user_id,
                "approved_at": {"$ne": None},
                "$or": [
                    {"reading.title": {"$regex": escape_regex(query), "$options": "i"}},
                    {"reading.body": {"$regex": escape_regex(query), "$options": "i"}},
                ],
            }
        ).to_list(length=top_k)
        return [load_entity(self._entity_class, document) for document in documents]


def escape_regex(text: str) -> str:
    """Escape regex metacharacters before a user-supplied pattern is used."""
    import re

    return re.escape(text)
