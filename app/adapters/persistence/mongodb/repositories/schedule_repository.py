"""MongoDB adapter for the ``ScheduleRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.schedule import Schedule


class ScheduleRepository(MongoRepository[Schedule]):
    entity_class = Schedule
    collection_name = "schedules"
    _PORT = "ScheduleRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "Schedule | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[Schedule]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def update(self, schedule: "Schedule") -> "Schedule":
        """Full update; version bump is the service's responsibility."""
        from app.adapters.persistence.mongodb.mappers import dump_entity

        document = dump_entity(schedule)
        await self.collection.replace_one(
            {"_id": document["_id"], "owner_user_id": schedule.owner_user_id},
            document,
            upsert=True,
        )
        return schedule

    async def delete(self, schedule_id: str, owner_user_id: str) -> bool:
        return await self.delete_one_by_id(schedule_id, owner_user_id)
