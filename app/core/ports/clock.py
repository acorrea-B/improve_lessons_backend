"""Clock"""
from __future__ import annotations

from datetime import datetime
from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self):
        """Return the current instant as a timezone-aware UTC datetime."""
        ...

