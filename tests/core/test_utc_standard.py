"""The mandatory UTC standard test suite (plan.md § Mandatory Standards,
quickstart.md § 9). The static no-implicit-local-time lint lives in
``tests/core/test_no_implicit_local_time.py`` (T027); this module keeps the
§ 9.1/§ 9.2/§ 9.4 fixture-level assertions."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.time.utc import (
    minutes_after,
    now_utc,
    parse_iso_to_utc,
    require_aware_utc,
    to_utc_instant,
)


class TestUtcStandardInvariants(unittest.TestCase):
    """§ 9.2 — persisted instants round-trip as aware UTC; the adapter and
    strategy layers raise on naive values (detailed adapter assertions live
    in tests/integration/test_summary_repository.py and
    tests/integration/test_user_repository.py)."""

    def test_naive_values_rejected_everywhere(self):
        with self.assertRaises(ValueError):
            require_aware_utc(datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            parse_iso_to_utc("2026-10-13T10:30:00")

    def test_offsets_normalized_at_boundaries(self):
        self.assertEqual(
            parse_iso_to_utc("2026-10-13T10:30:00-04:00"),
            datetime(2026, 10, 13, 14, 30, tzinfo=UTC),
        )

    def test_dst_transition_instant_classification(self):
        """Europe/Madrid leaves DST on 2026-10-25: instants adjacent to the
        transition keep their UTC deltas when shown as wall clock."""
        from app.core.time.wall_clock import wall_clock_in_zone

        before = datetime(2026, 10, 24, 12, 0, tzinfo=UTC).astimezone(ZoneInfo("Europe/Madrid"))
        after = datetime(2026, 10, 26, 12, 0, tzinfo=UTC).astimezone(ZoneInfo("Europe/Madrid"))
        self.assertEqual(before.tzname(), "CEST")
        self.assertEqual(after.tzname(), "CET")
        self.assertEqual(
            wall_clock_in_zone(before, "Europe/Madrid").tzname(), "CEST"
        )

    def test_minutes_after_keeps_utc(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(minutes_after(base, 30), datetime(2026, 1, 1, 0, 30, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()