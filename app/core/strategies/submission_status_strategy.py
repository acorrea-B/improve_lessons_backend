"""Submission-status strategy (T051, FR-025, FR-025a).

The 30-minute on-time window is evaluated as instants (UTC arithmetic);
the user's time zone is applied by the caller for wall-clock reporting.
The user's tz is validated at the boundary so a misconfigured zone cannot
silently change the classification.
"""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from app.core.entities.enums import SubmissionStatus
from app.core.errors import ValidationErrorDetail
from app.core.time.utc import require_aware_utc

SUBMISSION_WINDOW = timedelta(minutes=30)


def validate_time_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except Exception as exc:  # ZoneInfo raises ZoneInfoNotFoundError (KeyError)
        raise ValidationErrorDetail(
            code="invalid_time_zone",
            message="time_zone must be a valid IANA time zone identifier.",
            details={"field": "time_zone", "value": name},
            status_code=422,
        ) from exc
    return name


def zone_for(name: str) -> ZoneInfo:
    return ZoneInfo(name)


class SubmissionStatusStrategy:
    def derive(
        self,
        *,
        submitted_at,
        scheduled_start_at,
        scheduled_end_at,
    ) -> SubmissionStatus:
        submitted = require_aware_utc(submitted_at, argument="submitted_at")
        start = require_aware_utc(scheduled_start_at, argument="scheduled_start_at")
        end = require_aware_utc(scheduled_end_at, argument="scheduled_end_at")
        if submitted <= end + SUBMISSION_WINDOW:
            return SubmissionStatus.ON_TIME
        return SubmissionStatus.LATE

    def submitted_before_start(
        self, *, submitted_at, scheduled_start_at
    ) -> bool:
        submitted = require_aware_utc(submitted_at, argument="submitted_at")
        start = require_aware_utc(scheduled_start_at, argument="scheduled_start_at")
        return submitted < start