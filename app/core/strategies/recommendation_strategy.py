"""Recommendation strategy (FR-075 / FR-077, constitution VII & VIII).

The recommended challenge target NEVER exceeds the user's current CEFR
level by more than one level. Users with no demonstrated history start at
their declared level; users at the top of the scale receive refinements
within the same level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.entities.enums import CEFRLevel

if TYPE_CHECKING:
    from app.core.entities.enums import SubmissionStatus


@dataclass(frozen=True)
class Recommendation:
    target_cefr_level: CEFRLevel
    rationale: str
    kind: str  # "refinement" | "progression" | "starting"


class RecommendationStrategy:
    def recommend(
        self,
        *,
        declared_level: CEFRLevel,
        has_history: bool,
        recent_on_time_submissions: int = 0,
    ) -> Recommendation:
        """Resolve the challenge target level (never above declared + 1)."""
        if not has_history:
            return Recommendation(
                target_cefr_level=declared_level,
                rationale=(
                    "No documented history yet: the starting challenge is set "
                    "at the declared CEFR level (FR-077)."
                ),
                kind="starting",
            )
        upper_bound = _plus_one(declared_level)
        sustained = recent_on_time_submissions >= 3
        if not sustained:
            return Recommendation(
                target_cefr_level=declared_level,
                rationale=(
                    "Insufficient sustained evidence to progress: staying at "
                    "the declared level until consistent on-time work accumulates."
                ),
                kind="refinement",
            )
        return Recommendation(
            target_cefr_level=upper_bound,
            rationale=(
                f"Sustained on-time evidence allows one-level progression up to "
                f"{upper_bound} (FR-075: never more than CEFR + 1)."
            ),
            kind="progression",
        )


def _plus_one(level: CEFRLevel) -> CEFRLevel:
    next_level = level.next_level()
    if next_level is None:
        return level
    return next_level


def on_time_streak(statuses: "list[SubmissionStatus]") -> int:
    """Current consecutive on-time streak, newest submission first."""
    streak = 0
    for status in reversed(list(statuses)):
        from app.core.entities.enums import SubmissionStatus as _S

        if status is _S.ON_TIME:
            streak += 1
        else:
            break
    return streak


def longest_on_time_streak(statuses: "list[SubmissionStatus]") -> int:
    best = 0
    current = 0
    for status in statuses:
        if status.name == "ON_TIME":
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best