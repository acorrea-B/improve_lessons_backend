"""Common MongoDB repository plumbing (T019).

Every concrete repository:
- scopes every read and write by ``owner_user_id`` (defense in depth),
- applies the UTC invariant through ``mappers.dump_entity`` / ``load_entity``,
- maps ``DuplicateKeyError`` onto the domain ``ConflictError``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import dump_entity, load_entity
from app.core.entities.base import Entity
from app.core.errors import ConflictError, NotFoundError
from app.core.time.utc import now_utc, require_aware_utc

EntityT = TypeVar("EntityT", bound=BaseModel)


class MongoRepository(Generic[EntityT]):
    entity_class: type[BaseModel]
    collection_name: str

    def __init__(self, client: MongoClientWrapper) -> None:
        self._client = client
        self._entity_class = type(self).entity_class

    @property
    def collection(self):
        return self._client.database()[self.collection_name]

    async def insert(self, entity: EntityT, *, ignore_duplicate: bool = False) -> EntityT:
        document = dump_entity(entity)
        try:
            await self.collection.insert_one(document)
        except Exception as exc:  # DuplicateKeyError
            if ignore_duplicate and _is_duplicate_key(exc):
                return entity
            raise _map_duplicate(exc, self.collection_name) from exc
        return entity

    async def find_one(self, query: dict[str, Any]) -> EntityT | None:
        document = await self.collection.find_one(query)
        if document is None:
            return None
        return load_entity(self._entity_class, document)

    async def find_list(
        self, query: dict[str, Any], *, sort: list | None = None, limit: int | None = None
    ) -> list[EntityT]:
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if limit is not None:
            cursor = cursor.limit(limit)
        documents = await cursor.to_list(length=limit or 1000)
        return [load_entity(self._entity_class, document) for document in documents]

    async def replace(self, entity: EntityT, *, touch_updated_at: bool = True) -> EntityT:
        """Full-document replace by ``_id``; bumps ``version``/``updated_at``."""
        if touch_updated_at and "updated_at" in type(entity).model_fields:
            entity.updated_at = now_utc()  # type: ignore[assignment]
        if "version" in type(entity).model_fields:
            entity.version = int(getattr(entity, "version") or 1) + 1  # type: ignore[arg-type]
        document = dump_entity(entity)
        result = await self.collection.replace_one(
            {"_id": str(entity.id), "owner_user_id": str(getattr(entity, "owner_user_id", ""))},
            document,
        )
        if result.matched_count == 0:
            raise NotFoundError(
                "not_found",
                f"No {self.collection_name} document with id {entity.id} for this owner.",
            )
        return entity

    async def delete_one_by_id(self, entity_id: str, owner_user_id: str) -> bool:
        result = await self.collection.delete_one({"_id": entity_id, "owner_user_id": owner_user_id})
        return result.deleted_count == 1

    @staticmethod
    def as_id(value: UUID | str) -> str:
        return value if isinstance(value, str) else str(value)


def _is_duplicate_key(exc: Exception) -> bool:
    from pymongo.errors import DuplicateKeyError

    return isinstance(exc, DuplicateKeyError)


def _map_duplicate(exc: Exception, collection: str) -> ConflictError:
    from pymongo.errors import DuplicateKeyError

    if not isinstance(exc, DuplicateKeyError):
        raise exc
    details: dict[str, Any] = {"collection": collection}
    message = "A document with the same unique key already exists."
    if "session_id" in str(exc):
        code = "summary_already_exists"
        message = "A summary for this session has already been submitted."
        details = {"field": "session_id"}
    elif "summary_id" in str(exc):
        code = "material_already_exists"
        message = "A material for this summary/period has already been approved."
        details = {"field": "summary_id"}
    elif "email" in str(exc):
        code = "email_already_registered"
        message = "An account with this email already exists."
        details = {"field": "email"}
    else:
        code = "duplicate_resource"
    return ConflictError(code, message, details)

def _add_get_by_id_alias():
    """Every generated repository exposes ``get_by_id`` (owner-scoped) as
    an alias for ``get``; the port contract consistently names it that way."""
    def get_by_id(self, entity_id: str, owner_user_id: str):
        return self.get(entity_id, owner_user_id)
    MongoRepository.get_by_id = get_by_id


_add_get_by_id_alias()
