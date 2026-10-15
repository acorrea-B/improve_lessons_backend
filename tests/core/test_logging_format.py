"""Logging configuration tests (T013, quickstart § 9.4): the asctime is a
``Z``-suffixed UTC instant regardless of the host's local time zone."""

from __future__ import annotations

import logging
import re
import unittest
from datetime import datetime

from app.utils.logging import (
    UTCFormatter,
    SecretRedactingFilter,
    configure_logging,
)

Z_SUFFIXED = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z \| INFO \| t \| hello$"
)


class TestLoggingFormat(unittest.TestCase):
    def test_formatter_emits_z_suffixed_utc_instant(self):
        formatter = UTCFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
        formatted = formatter.format(record)
        self.assertIsNotNone(Z_SUFFIXED.match(formatted), formatted)
        asctime = formatted.split(" | ")[0].replace("Z", "+00:00")
        datetime.fromisoformat(asctime)  # a valid ISO instant

    def test_secret_redacting_filter(self):
        record = logging.LogRecord(
            "t", logging.INFO, __file__, 1,
            "auth failed: api_key=supersecret token=abc", None, None,
        )
        SecretRedactingFilter().filter(record)
        self.assertNotIn("supersecret", record.msg)
        self.assertNotIn("abc", record.msg)


class TestConfigureLogging(unittest.TestCase):
    def test_configure_is_idempotent(self):
        configure_logging()
        configure_logging()
        logger = logging.getLogger("improve_lessons")
        self.assertFalse(logger.propagate)
        self.assertEqual(len(logger.handlers), 1)


if __name__ == "__main__":
    unittest.main()