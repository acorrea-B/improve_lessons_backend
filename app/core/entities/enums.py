"""Shared domain enums (data-model.md)."""

from __future__ import annotations

from enum import StrEnum


class CEFRLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

    def next_level(self) -> "CEFRLevel | None":
        """The level immediately above self, or None at the top (C2)."""
        order = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1,
                 CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
        index = order.index(self)
        return order[index + 1] if index + 1 < len(order) else None


class Modality(StrEnum):
    IN_PERSON = "in_person"
    VIRTUAL = "virtual"


class Recurrence(StrEnum):
    DAILY = "daily"
    EVERY_OTHER_DAY = "every_other_day"


class SubmissionStatus(StrEnum):
    ON_TIME = "on_time"
    LATE = "late"


class Verdict(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"