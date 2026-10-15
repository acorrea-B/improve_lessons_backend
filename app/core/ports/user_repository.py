"""UserRepository"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.entities.user import User

from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> "User | None": ...

    @abstractmethod
    async def get_by_email(self, email: str) -> "User | None": ...

    @abstractmethod
    async def insert(self, user: "User") -> "User": ...

    @abstractmethod
    async def update(self, user: "User") -> "User": ...

