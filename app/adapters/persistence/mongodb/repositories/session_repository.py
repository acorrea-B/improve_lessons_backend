"""MongoDB adapter for the ``SessionRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.session import Session


class SessionRepository(MongoRepository[Session]):
    entity_class = Session
    collection_name = "sessions"
    _PORT = "SessionRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "Session | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[Session]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert_many(self, sessions: "list[Session]") -> "list[Session]":
        """Idempotent upsert keyed on (schedule_id, scheduled_start_at):
        re-expanding a schedule must not duplicate or reshuffle ids."""
        inserted: list[Session] = []
        for session in sessions:
            document = self._dump(session)
            stored_id = document.pop("_id")
            await self.collection.update_one(
                {
                    "schedule_id": document["schedule_id"],
                    "scheduled_start_at": document["scheduled_start_at"],
                },
                {"$set": document, "$setOnInsert": {"_id": stored_id}},
                upsert=True,
            )
            inserted.append(session)
        return inserted

    async def list_for_owner(
        self, owner_user_id: str, *, from_instant=None, to_instant=None
    ) -> "list[Session]":
        query: dict = {"owner_user_id": owner_user_id}
        range_filter: dict = {}
        if from_instant is not None:
            range_filter["$gte"] = from_instant
        if to_instant is not None:
            range_filter["$lt"] = to_instant
        if range_filter:
            query["scheduled_start_at"] = range_filter
        return await self.find_list(
            query, sort=[("scheduled_start_at", 1)], limit=5000
        )

    async def list_pending_reminders(self, window_start, window_end) -> "list[Session]":
        return await self.find_list(
            {
                "scheduled_start_at": {"$gte": window_start, "$lt": window_end},
                "reminder_sent_at": None,
            },
            limit=1000,
        )

    async def update(self, session: "Session") -> "Session":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(session)
        await self.collection.update_one(
            {"_id": document["_id"], "owner_user_id": session.owner_user_id},
            {"$set": document},
            upsert=True,
        )
        return session

    async def delete_future_for_schedule(self, schedule_id: str, now) -> int:
        result = await self.collection.delete_many(
            {"schedule_id": schedule_id, "scheduled_start_at": {"$gte": now}}
        )
        return result.deleted_count

    def _dump(self, entity):
        from app.adapters.persistence.mongodb.mappers import dump_entity
        return dump_entity(entity)
