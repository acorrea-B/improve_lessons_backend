"""Authenticator port (T014, research.md § 7).

The concrete mechanism is a deferred decision; the port fixes the
contract: issue a token for a principal and return the authenticated
principal (id + issued instant) when a token is valid. ``issued_at`` lets
the caller enforce logout revocation (``users.session_valid_after``)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class Principal:
    user_id: str


@dataclass
class AuthContext:
    user_id: str
    issued_at: datetime


class Authenticator(ABC):
    @abstractmethod
    async def issue_token(self, user_id: str) -> str: ...

    @abstractmethod
    async def authenticate(self, token: str) -> "AuthContext | None":
        """Return the authenticated principal, or None when invalid."""
        ...