"""IdempotencyStore port (T030, contract § Conventions).

Stores the response produced for every (owner, key, method, path) so a
repeated write replays the original response verbatim."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.feature_availability import IdempotencyRecord


class IdempotencyStore(ABC):
    @abstractmethod
    async def find(
        self, owner_user_id: str, idempotency_key: str, method: str, path: str
    ) -> "IdempotencyRecord | None": ...

    @abstractmethod
    async def insert(self, record: "IdempotencyRecord") -> bool:
        """Insert an in-flight lease; False when the key already holds one."""

    @abstractmethod
    async def update_response(
        self,
        owner_user_id: str,
        idempotency_key: str,
        method: str,
        path: str,
        *,
        status_code: int,
        response_body: str,
    ) -> bool: ...
