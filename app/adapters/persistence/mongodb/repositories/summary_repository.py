"""MongoDB adapter for the ``SummaryRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.daily_summary import DailySummary


class SummaryRepository(MongoRepository[DailySummary]):
    entity_class = DailySummary
    collection_name = "daily_summaries"
    _PORT = "SummaryRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "DailySummary | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[DailySummary]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert(self, summary: "DailySummary") -> "DailySummary":
        """Insert-only: DuplicateKeyError on ``session_id`` maps to
        ``summary_already_exists`` (FR-024a)."""
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(summary)
        try:
            await self.collection.insert_one(document)
        except Exception as exc:
            raise self._duplicate(exc) from exc
        return summary

    async def get_by_session(self, session_id: str, owner_user_id: str) -> "DailySummary | None":
        return await self.find_one({"session_id": session_id, "owner_user_id": owner_user_id})

    async def list_for_owner(
        self, owner_user_id: str, *, from_instant=None, to_instant=None
    ) -> "list[DailySummary]":
        query: dict = {"owner_user_id": owner_user_id}
        if from_instant is not None or to_instant is not None:
            range_filter: dict = {}
            if from_instant is not None:
                range_filter["$gte"] = from_instant
            if to_instant is not None:
                range_filter["$lt"] = to_instant
            query["submitted_at"] = range_filter
        return await self.find_list(query, sort=[("submitted_at", 1)], limit=5000)

    @staticmethod
    def _duplicate(exc: Exception) -> Exception:
        from app.adapters.persistence.mongodb.repositories.base import _map_duplicate
        try:
            return _map_duplicate(exc, "daily_summaries")
        except Exception as mapped:
            return mapped if isinstance(mapped, Exception) else exc
