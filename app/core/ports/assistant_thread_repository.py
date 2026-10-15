"""AssistantThreadRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.summary_chunk import AssistantThread, ThreadMessage

from abc import ABC, abstractmethod


class AssistantThreadRepository(ABC):
    @abstractmethod
    async def insert(self, thread: "AssistantThread") -> "AssistantThread": ...

    @abstractmethod
    async def get(self, thread_id: str, owner_user_id: str) -> "AssistantThread | None": ...

    @abstractmethod
    async def list_for_owner(self, owner_user_id: str) -> "list[AssistantThread]": ...

    @abstractmethod
    async def append_message(self, thread_id: str, owner_user_id: str, message: "ThreadMessage") -> "AssistantThread | None": ...

    @abstractmethod
    async def set_context_refs(
        self, thread_id: str, owner_user_id: str, context_refs: "list[str]"
    ) -> "AssistantThread | None": ...

