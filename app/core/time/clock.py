"""Concrete clock implementations for the ``Clock`` port (T014).

- ``SystemClock``: the real system clock, only ever returning UTC.
- ``ScheduledClock``: test/worker helper that replays a fixed schedule of
  instants in sequence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from app.core.time.utc import now_utc


class SystemClock:
    """Default clock; always returns a timezone-aware UTC instant."""

    def now(self) -> datetime:
        return now_utc()


class ScheduledClock:
    """Deterministic clock used by the reminder worker and tests.

    Returns the scheduled instants in order; when the list is exhausted the
    last instant is returned forever.
    """

    def __init__(self, schedule: Iterable[datetime]) -> None:
        self._pending: list[datetime] = list(schedule)
        self._current: datetime | None = None

    def now(self) -> datetime:
        if self._pending:
            self._current = self._pending.pop(0)
        elif self._current is None:
            self._current = now_utc()
        return self._current

    def advance_to(self, instant: datetime) -> None:
        self._current = instant
        self._pending = []

    def schedule(self, instants: Sequence[datetime]) -> None:
        self._pending = list(instants)