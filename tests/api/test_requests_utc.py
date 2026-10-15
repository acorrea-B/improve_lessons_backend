"""UTC contract unit checks for the request/response models
(quickstart.md § 9.1). These run without the live backend: the Pydantic
`AwareDatetime` annotation is the single enforcement point the contract
documented."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from app.api.v1.requests import TimestampProbeRequest
from app.core.time.utc import AwareDatetime


class TestUTCContract(unittest.TestCase):
    def test_z_suffix_accepted_and_normalized(self):
        probe = TimestampProbeRequest.model_validate(
            {"submitted_at": "2026-10-13T14:30:00Z"}
        )
        self.assertEqual(probe.submitted_at, datetime(2026, 10, 13, 14, 30, tzinfo=UTC))
        self.assertEqual(
            probe.model_dump(mode="json")["submitted_at"], "2026-10-13T14:30:00Z"
        )

    def test_explicit_offset_accepted_and_normalized(self):
        probe = TimestampProbeRequest.model_validate(
            {"submitted_at": "2026-10-13T10:30:00-04:00"}
        )
        self.assertEqual(
            probe.model_dump(mode="json")["submitted_at"], "2026-10-13T14:30:00Z"
        )

    def test_naive_timestamp_rejected_as_invalid_timestamp(self):
        with self.assertRaises(ValidationError) as ctx:
            TimestampProbeRequest.model_validate({"submitted_at": "2026-10-13T10:30:00"})
        errors = ctx.exception.errors()
        self.assertTrue(all("invalid_timestamp" in str(error["msg"]) for error in errors))

    def test_explicit_offsets_are_never_emitted(self):
        probe = TimestampProbeRequest.model_validate(
            {"submitted_at": "2026-10-13T09:00:00+02:00"}
        )
        emitted = probe.model_dump(mode="json")["submitted_at"]
        self.assertTrue(emitted.endswith("Z"))
        self.assertNotIn("+0", emitted)

    def test_none_is_allowed_for_optional_instants(self):
        probe = TimestampProbeRequest.model_validate({})
        self.assertIsNone(probe.submitted_at)


if __name__ == "__main__":
    unittest.main()