"""Strategy implementations (T016). Depend only on ``app/core/time/`` and
pydantic."""

from app.core.strategies.month_boundary_strategy import (
    month_end_for_wall_clock,
    month_start_for_wall_clock,
    resolve_month,
)
from app.core.strategies.recommendation_strategy import (
    Recommendation,
    RecommendationStrategy,
    longest_on_time_streak,
    on_time_streak,
)
from app.core.strategies.submission_status_strategy import (
    SubmissionStatusStrategy,
    validate_time_zone,
    zone_for,
)
from app.core.strategies.week_boundary_strategy import (
    WeekBoundaryStrategy,
    resolve_day,
    week_end_for_wall_clock,
    week_start_for_wall_clock,
)

__all__ = [
    "longest_on_time_streak",
    "on_time_streak",
    "month_end_for_wall_clock",
    "month_start_for_wall_clock",
    "Recommendation",
    "RecommendationStrategy",
    "resolve_month",
    "SubmissionStatusStrategy",
    "validate_time_zone",
    "zone_for",
    "WeekBoundaryStrategy",
    "resolve_day",
    "week_end_for_wall_clock",
    "week_start_for_wall_clock",
]