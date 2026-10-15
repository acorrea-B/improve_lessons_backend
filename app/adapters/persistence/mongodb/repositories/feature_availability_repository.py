"""MongoDB adapter for the ``FeatureAvailabilityRepository`` port (T019)."""

from __future__ import annotations


from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import load_entity
from app.adapters.persistence.mongodb.repositories.base import MongoRepository

from app.core.entities.feature_availability import FeatureAvailability


class FeatureAvailabilityRepository(MongoRepository[FeatureAvailability]):
    entity_class = FeatureAvailability
    collection_name = "feature_availability_config"
    _PORT = "FeatureAvailabilityRepository"

    async def get(self, entity_id: str, owner_user_id: str) -> "FeatureAvailability | None":
        return await self.find_one({"_id": entity_id, "owner_user_id": owner_user_id})

    async def list_for_owner(self, owner_user_id: str) -> "list[FeatureAvailability]":
        return await self.find_list({"owner_user_id": owner_user_id})

    async def get(self, feature: str) -> "FeatureAvailability | None":
        document = await self.collection.find_one({"_id": feature})
        if document is None:
            return None
        from app.adapters.persistence.mongodb.mappers import load_entity
        loaded = dict(document)
        loaded["id"] = loaded.pop("_id")
        return load_entity(self._entity_class, loaded)

    async def set(self, availability: "FeatureAvailability") -> "FeatureAvailability":
        from app.adapters.persistence.mongodb.mappers import dump_entity
        document = dump_entity(availability)
        document["_id"] = str(availability.id)  # feature name
        await self.collection.update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )
        return availability

    async def list_all(self) -> "list[FeatureAvailability]":
        from app.adapters.persistence.mongodb.mappers import load_entity
        documents = await self.collection.find({}).to_list(length=100)
        entities = []
        for document in documents:
            loaded = dict(document)
            loaded["id"] = loaded.pop("_id")
            entities.append(load_entity(self._entity_class, loaded))
        return entities
