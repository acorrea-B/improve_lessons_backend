"""UTC helper unit tests (T012): naive rejection, normalization, and the
 AwareDatetime Pydantic annotation."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta, tzinfo

from pydantic import BaseModel

from app.core.time.utc import (
    AwareDatetime,
    minutes_after,
    now_utc,
    parse_iso_to_utc,
    require_aware_utc,
    to_utc_instant,
)


class Probe(BaseModel):
    at: AwareDatetime


class TestNowUtc(unittest.TestCase):
    def test_now_utc_is_aware(self):
        now = now_utc()
        self.assertIsNotNone(now.tzinfo)

    def test_require_aware_utc_rejects_naive(self):
        with self.assertRaises(ValueError):
            require_aware_utc(datetime(2026, 1, 1))


class TestParseIsoToUtc(unittest.TestCase):
    def test_offset_is_normalized(self):
        result = parse_iso_to_utc("2026-10-13T10:30:00-04:00")
        self.assertEqual(result, datetime(2026, 10, 13, 14, 30, tzinfo=UTC))

    def test_z_suffix_accepted(self):
        result = parse_iso_to_utc("2026-10-13T14:30:00Z")
        self.assertEqual(result, datetime(2026, 10, 13, 14, 30, tzinfo=UTC))

    def test_naive_string_rejected_with_invalid_timestamp(self):
        with self.assertRaises(ValueError) as ctx:
            parse_iso_to_utc("2026-10-13T10:30:00")
        self.assertTrue(str(ctx.exception).startswith("invalid_timestamp"))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            parse_iso_to_utc("   ")
        self.assertTrue(str(ctx.exception).startswith("invalid_timestamp"))


class TestAwareDatetimeAnnotation(unittest.TestCase):
    def test_offset_normalized_on_validation(self):
        probe = Probe.model_validate({"at": "2026-10-13T10:30:00-04:00"})
        self.assertEqual(probe.at, datetime(2026, 10, 13, 14, 30, tzinfo=UTC))

    def test_serialization_emits_z_suffix(self):
        probe = Probe(at=datetime(2026, 10, 13, 14, 30, tzinfo=UTC))
        self.assertEqual(probe.model_dump(mode="json")["at"], "2026-10-13T14:30:00Z")


class TestToUtcInstant(unittest.TestCase):
    def test_converts_offset(self):
        instant = datetime(2026, 1, 1, tzinfo=ZoneInfoStub())
        self.assertEqual(to_utc_instant(instant).tzinfo, UTC)


class ZoneInfoStub(tzinfo):  # +05:30 for an easy conversion assertion

    def utcoffset(self, dt): return timedelta(hours=5, minutes=30)

    def tzname(self, dt): return "FIXED+0530"

    def dst(self, dt): return timedelta(0)

    def fromutc(self, dt):
        return dt + self.utcoffset(dt)

    def fromutc(self, dt):
        from datetime import timedelta
        return dt + timedelta(hours=5, minutes=30)


class TestMinutesAfter(unittest.TestCase):
    def test_adds_minutes(self):
        base = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(minutes_after(base, 30), datetime(2026, 1, 1, 0, 30, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()