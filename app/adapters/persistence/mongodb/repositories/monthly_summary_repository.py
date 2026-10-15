"""MongoDB adapter for the ``MonthlySummaryRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.materials import MonthlySummary


class MonthlySummaryRepository(MongoRepository[MonthlySummary]):
    entity_class = MonthlySummary
    collection_name = "monthly_summaries"
    _PORT = "MonthlySummaryRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "MonthlySummary | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[MonthlySummary]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def get_by_period(self, owner_user_id: str, month_start_at) -> "MonthlySummary | None":
        return await self.find_one(
            {"owner_user_id": owner_user_id, "month_start_at": month_start_at}
        )

    async def list_for_owner(self, owner_user_id: str, *, from_instant=None, to_instant=None) -> "list[MonthlySummary]":
        query: dict = {"owner_user_id": owner_user_id}
        if from_instant is not None or to_instant is not None:
            range_filter: dict = {}
            if from_instant is not None:
                range_filter["$gte"] = from_instant
            if to_instant is not None:
                range_filter["$lt"] = to_instant
            query["month_start_at"] = range_filter
        return await self.find_list(query, sort=[("month_start_at", 1)], limit=1000)

    async def update(self, summary: "MonthlySummary") -> "MonthlySummary":
        """Upsert by (owner, period); updates the attached material id."""
        from app.adapters.persistence.mongodb.mappers import dump_entity

        document = dump_entity(summary)
        await self.collection.update_one(
            {"_id": document["_id"], "owner_user_id": summary.owner_user_id},
            {"$set": document},
            upsert=True,
        )
        return summary
