"""Strategy unit tests (T016 / T051): submission windows, week/month
boundaries and the CEFR + 1 recommendation bound, across time zones."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.entities.enums import CEFRLevel, Recurrence, SubmissionStatus
from app.core.errors import ValidationErrorDetail
from app.core.strategies import (
    RecommendationStrategy,
    SubmissionStatusStrategy,
    WeekBoundaryStrategy,
    month_end_for_wall_clock,
    month_start_for_wall_clock,
    resolve_month,
    validate_time_zone,
)


def local_instant(tz: str, hour: int, minute: int = 0, day: int = 14) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo(tz))


class TestSubmissionStatusStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = SubmissionStatusStrategy()

    def test_on_time_within_30_minutes(self):
        start = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        end = start + timedelta(minutes=60)
        submitted = end + timedelta(minutes=29)
        self.assertEqual(
            self.strategy.derive(
                submitted_at=submitted,
                scheduled_start_at=start,
                scheduled_end_at=end,
            ),
            SubmissionStatus.ON_TIME,
        )

    def test_on_time_exactly_at_boundary(self):
        start = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        end = start + timedelta(minutes=60)
        self.assertEqual(
            self.strategy.derive(
                submitted_at=end + timedelta(minutes=30),
                scheduled_start_at=start,
                scheduled_end_at=end,
            ),
            SubmissionStatus.ON_TIME,
        )

    def test_late_beyond_window(self):
        start = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)
        end = start + timedelta(minutes=60)
        submitted = end + timedelta(minutes=31)
        self.assertEqual(
            self.strategy.derive(
                submitted_at=submitted,
                scheduled_start_at=start,
                scheduled_end_at=end,
            ),
            SubmissionStatus.LATE,
        )

    def test_user_time_zone_does_not_change_classification(self):
        """UTC normalization is independent of the user's local clock."""
        for tz in ("America/Bogota", "Europe/Madrid", "Asia/Kolkata"):
            local = local_instant(tz, 9)
            status = self.strategy.derive(
                submitted_at=local + timedelta(minutes=45),
                scheduled_start_at=local + timedelta(minutes=60),
                scheduled_end_at=local + timedelta(minutes=60),
            )
            self.assertEqual(status, SubmissionStatus.ON_TIME, tz)

    def test_pre_start_flag(self):
        submitted = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
        start = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
        self.assertTrue(
            self.strategy.submitted_before_start(
                submitted_at=submitted, scheduled_start_at=start
            )
        )

    def test_naive_submitted_at_rejected(self):
        with self.assertRaises(ValueError):
            self.strategy.derive(
                submitted_at=datetime(2026, 10, 14, 15, 0),
                scheduled_start_at=datetime(2026, 10, 14, 14, 0, tzinfo=UTC),
                scheduled_end_at=datetime(2026, 10, 14, 16, 0, tzinfo=UTC),
            )


class TestWeekBoundaryStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = WeekBoundaryStrategy()

    def test_monday_start_in_user_timezone(self):
        # 2026-10-14 is a Wednesday. The stored instants are UTC; the
        # Monday-00:00 property holds in the USER's wall clock.
        for tz in ("America/Bogota", "Europe/Madrid", "Asia/Kolkata"):
            trigger = local_instant(tz, 10)
            start, end = self.strategy.resolve(trigger, tz)
            local_start = start.astimezone(ZoneInfo(tz))
            self.assertEqual(local_start.weekday(), 0, tz)
            self.assertEqual((local_start.hour, local_start.minute), (0, 0), tz)
            self.assertEqual((end - start).days, 7, tz)
            self.assertEqual(start.tzinfo, UTC, tz)

    def test_dst_crossing_keeps_classification(self):
        # Europe/Madrid DST ends 2026-10-25 (CET); a week spanning the end
        # of DST still has exactly 168 hours but shifts wall-clock offsets.
        trigger = datetime(2026, 10, 20, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        start, end = self.strategy.resolve(trigger, "Europe/Madrid")
        self.assertEqual((end - start).days, 7)

    def test_resolve_day_requires_monday(self):
        with self.assertRaises(ValueError):
            self.strategy.resolve_local_day("2026-10-14", "UTC")  # Wednesday
        start, end = self.strategy.resolve_local_day("2026-10-12", "UTC")
        self.assertEqual(start.weekday(), 0)


class TestMonthBoundaryStrategy(unittest.TestCase):
    def test_calendar_month_in_user_tz(self):
        for tz in ("America/Bogota", "Europe/Madrid"):
            start = month_start_for_wall_clock(local_instant(tz, 10), tz)
            end = month_end_for_wall_clock(start, tz)
            local_start = start.astimezone(ZoneInfo(tz))
            self.assertEqual((local_start.day, local_start.month), (1, 10), tz)

    def test_resolve_month(self):
        start, end = resolve_month("2026-02", "UTC")
        self.assertEqual(end.month, 3)
        self.assertEqual((end - start).days, 28)


class TestRecommendationStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = RecommendationStrategy()

    def test_no_history_starts_at_declared_level(self):
        result = self.strategy.recommend(
            declared_level=CEFRLevel.A1, has_history=False
        )
        self.assertEqual(result.target_cefr_level, CEFRLevel.A1)
        self.assertEqual(result.kind, "starting")

    def test_never_exceeds_cefr_plus_one(self):
        result = self.strategy.recommend(
            declared_level=CEFRLevel.B1,
            has_history=True,
            recent_on_time_submissions=10,
        )
        self.assertEqual(result.target_cefr_level, CEFRLevel.B2)

    def test_top_level_receives_refinements(self):
        result = self.strategy.recommend(
            declared_level=CEFRLevel.C2,
            has_history=True,
            recent_on_time_submissions=10,
        )
        self.assertEqual(result.target_cefr_level, CEFRLevel.C2)

    def test_unsustained_stays_at_level(self):
        result = self.strategy.recommend(
            declared_level=CEFRLevel.B1,
            has_history=True,
            recent_on_time_submissions=1,
        )
        self.assertEqual(result.target_cefr_level, CEFRLevel.B1)
        self.assertEqual(result.kind, "refinement")


class TestZoneValidation(unittest.TestCase):
    def test_valid_and_invalid_time_zones(self):
        self.assertEqual(validate_time_zone("America/Bogota"), "America/Bogota")
        with self.assertRaises(ValidationErrorDetail):
            validate_time_zone("Mars/Olympus")


if __name__ == "__main__":
    unittest.main()