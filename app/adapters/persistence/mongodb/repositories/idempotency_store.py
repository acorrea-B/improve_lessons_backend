"""MongoDB adapter for the ``IdempotencyStore`` port (T030)."""

from __future__ import annotations

from pymongo.errors import DuplicateKeyError
from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import dump_entity, load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.feature_availability import IdempotencyRecord


class IdempotencyStore(MongoRepository["IdempotencyRecord"]):
    entity_class = IdempotencyRecord
    collection_name = "idempotency_keys"
    _PORT = "IdempotencyStore"

    _KEY = "owner_user_id,idempotency_key,method,path"

    async def index(self) -> None:
        await self.collection.create_index(
            [("owner_user_id", 1), ("idempotency_key", 1), ("method", 1), ("path", 1)],
            unique=True,
            name="idempotency_unique",
        )
        from datetime import timedelta

        from app.core.time.utc import now_utc

        await self.collection.create_index(
            "expires_at", expireAfterSeconds=0, name="idempotency_ttl"
        )

    async def find(
        self, owner_user_id: str, idempotency_key: str, method: str, path: str
    ) -> "IdempotencyRecord | None":
        return await self.find_one(
            {
                "owner_user_id": owner_user_id,
                "idempotency_key": idempotency_key,
                "method": method,
                "path": path,
            }
        )

    async def insert(self, record: "IdempotencyRecord") -> bool:
        document = dump_entity(record)
        document["owner_user_id"] = record.owner_user_id
        document["idempotency_key"] = record.idempotency_key
        document["method"] = record.method
        document["path"] = record.path
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError:
            return False
        return True

    async def update_response(
        self,
        owner_user_id: str,
        idempotency_key: str,
        method: str,
        path: str,
        *,
        status_code: int,
        response_body: str,
    ) -> bool:
        result = await self.collection.update_one(
            {
                "owner_user_id": owner_user_id,
                "idempotency_key": idempotency_key,
                "method": method,
                "path": path,
            },
            {"$set": {"status_code": status_code, "response_body": response_body}},
        )
        return result.modified_count == 1
