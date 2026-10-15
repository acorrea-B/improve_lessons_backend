"""SecretProvider"""
from __future__ import annotations


from abc import ABC, abstractmethod


class SecretProvider(ABC):
    @abstractmethod
    async def get_secret(self, name: str) -> str:
        """Return the secret value; raises ConfigurationError when absent."""
        ...

