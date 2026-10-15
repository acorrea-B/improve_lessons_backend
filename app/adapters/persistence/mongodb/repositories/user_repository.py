"""MongoDB adapter for the ``UserRepository`` port (T019).

Users ARE their own owner: the collection has no ``owner_user_id``
field — every lookup keys on ``_id`` (the authenticated principal) or the
unique email. The UTC invariant applies through the shared mappers.
"""

from __future__ import annotations

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.mappers import dump_entity, load_entity
from app.adapters.persistence.mongodb.repositories.base import _map_duplicate
from app.adapters.persistence.mongodb.repositories.base import MongoRepository
from app.core.entities.user import User


class UserRepository(MongoRepository[User]):
    entity_class = User
    collection_name = "users"
    _PORT = "UserRepository"

    def __init__(self, client: MongoClientWrapper) -> None:
        super().__init__(client)
        # The base class owner-scopes queries by ``owner_user_id``; the
        # users collection has no such field, so lookups key on ``_id``.
        self._owner_scoped = False

    async def get_by_id(self, entity_id: str) -> "User | None":
        return await self.find_one({"_id": entity_id})

    async def get_by_email(self, email: str) -> "User | None":
        return await self.find_one({"email": email.lower()})

    async def insert_user(self, user: "User") -> "User":
        document = dump_entity(user)
        document["email"] = str(document["email"]).lower()
        try:
            await self.collection.insert_one(document)
        except Exception as exc:
            raise _map_duplicate(exc, self.collection_name) from exc
        return user

    async def update(self, user: "User") -> "User":
        from app.core.time.utc import now_utc

        user.updated_at = now_utc()
        user.version = user.version + 1
        document = dump_entity(user)
        document["email"] = str(document["email"]).lower()
        result = await self.collection.replace_one({"_id": document["_id"]}, document)
        if result.matched_count == 0:
            from app.core.errors import NotFoundError

            raise NotFoundError("user_not_found", f"No user {document['_id']}.")
        return user