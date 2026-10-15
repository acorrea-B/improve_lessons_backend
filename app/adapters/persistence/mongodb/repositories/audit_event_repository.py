"""MongoDB adapter for the ``AuditEventRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.feature_availability import AuditEvent


class AuditEventRepository(MongoRepository[AuditEvent]):
    entity_class = AuditEvent
    collection_name = "audit_events"
    _PORT = "AuditEventRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "AuditEvent | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[AuditEvent]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def insert(self, event: "AuditEvent") -> "AuditEvent":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(event)
        if event.owner_user_id is None:
            document.pop("owner_user_id", None)
        await self.collection.insert_one(document)
        return event

    async def list_for_owner(self, owner_user_id: str, *, limit: int = 100) -> "list[AuditEvent]":
        return await self.find_list({"owner_user_id": owner_user_id}, sort=[("created_at", -1)], limit=limit)
