"""Project logging configuration (T013, research.md § 8).

- Format: ``%(asctime)s | %(levelname)s | %(name)s | %(message)s``
- ``propagate=False`` on the project logger (no double logging).
- ``report_error`` / ``report_info`` helpers used instead of ``print()``.
- ``asctime`` is an ISO 8601 UTC instant with the ``Z`` suffix, regardless
  of the host's local time zone (plan.md § Mandatory Standards, rule 6).
- No ``print()`` and no credentials/secret values in log output.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import UTC, datetime

PROJECT_LOGGER_NAME = "improve_lessons"

# Never let these reach the log output even if a caller passes them by
# mistake (values are masked, keys are redacted entirely).
_SECRET_KEY_PATTERN = re.compile(
    r"(api[-_]?key|secret|password|token|authorization)[\s]*[=:>][\s]*(\S+)",
    re.IGNORECASE,
)
_SECRET_MASK = r"\1=<redacted>"


class UTCFormatter(logging.Formatter):
    """Formatter emitting ISO 8601 UTC instants with the ``Z`` suffix."""

    def formatTime(self, record: logging.LogRecord, datefmt=None):  # noqa: N802
        return (
            datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )


class SecretRedactingFilter(logging.Filter):
    """Masks anything that looks like a credential before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_KEY_PATTERN.sub(_SECRET_MASK, record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SECRET_KEY_PATTERN.sub(_SECRET_MASK, arg)
                if isinstance(arg, str)
                else arg
                for arg in record.args
            )
        return True


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the project logger. Idempotent (safe to call again)."""
    logger = logging.getLogger(PROJECT_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            UTCFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        handler.addFilter(SecretRedactingFilter())
        logger.addHandler(handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child of the project logger (always non-propagating)."""
    configure_logging()
    if name:
        return logging.getLogger(f"{PROJECT_LOGGER_NAME}.{name}")
    return logging.getLogger(PROJECT_LOGGER_NAME)


def report_info(event: str, message: str, **fields: object) -> None:
    """Structured info log entry: ``event | message | key=value ...``."""
    extras = " ".join(f"{key}={value}" for key, value in fields.items())
    get_logger().info("%s | %s%s", event, message, f" | {extras}" if extras else "")


def report_error(event: str, message: str, **fields: object) -> None:
    """Structured error log entry with the same envelope as ``report_info``."""
    extras = " ".join(f"{key}={value}" for key, value in fields.items())
    get_logger().error("%s | %s%s", event, message, f" | {extras}" if extras else "")


# ``configure`` is the name required by the runtime-image validation in
# quickstart.md § 9.5.
configure = configure_logging