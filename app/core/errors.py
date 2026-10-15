"""Domain errors shared by every layer (T024 maps these to HTTP statuses).

A ``DomainError`` carries a machine-readable ``code``; the API layer's
global error handler converts it into the documented error envelope:

    { "error": { "code", "message", "details" } }
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all domain errors raised inside ``app/``."""

    #: Default HTTP status used by the API error handler when the concrete
    #: subclass does not define one.
    status_code: int = 400

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code

    def to_envelope(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": dict(self.details),
            }
        }


class ValidationErrorDetail(DomainError):
    """Field-level validation failure → 422 Unprocessable Entity."""

    status_code = 422


class InvalidTimestampError(DomainError):
    """Naive or malformed timestamp → 400 with code ``invalid_timestamp``."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__("invalid_timestamp", message, details)


class UnauthorizedError(DomainError):
    status_code = 401


class ForbiddenError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ServiceUnavailableError(DomainError):
    status_code = 503

    def __init__(
        self, code: str, message: str, retry_after_seconds: int = 30
    ) -> None:
        super().__init__(code, message, status_code=503)
        self.retry_after_seconds = retry_after_seconds


class ConfigurationError(DomainError):
    """Missing/invalid mandatory configuration — the process refuses to start."""

    status_code = 500


class FeatureUnavailableError(DomainError):
    """A disabled feature was requested (US-13)."""

    status_code = 403

    def __init__(self, feature: str) -> None:
        super().__init__(
            "feature_not_available",
            f"The '{feature}' feature is not currently available.",
            details={"feature": feature},
        )
        self.feature = feature