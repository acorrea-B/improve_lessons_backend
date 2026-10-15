"""Global error handlers (T024).

Produces the documented envelope ``{"error": {"code", "message",
"details"}}`` and maps domain codes to HTTP statuses per
``contracts/README.md``:
- ``invalid_timestamp`` → 400 Bad Request,
- validation failures → 422,
- state-machine conflicts → 409,
- unauthenticated → 401, forbidden → 403, not found → 404,
- transient infrastructure → 503 with ``Retry-After``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    ConfigurationError,
    DomainError,
    FeatureUnavailableError,
    InvalidTimestampError,
    ServiceUnavailableError,
)
from app.utils.logging import get_logger, report_error

logger = get_logger("api.errors")


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope: dict = {"error": {"code": code, "message": message}}
    if details:
        envelope["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=envelope, headers=headers)


def _is_invalid_timestamp(exc: RequestValidationError) -> bool:
    for error in exc.errors():
        message = str(error.get("msg", ""))
        if "invalid_timestamp" in message or "invalid_HHMM" in message:
            return True
    return False


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        headers = None
        if isinstance(exc, ServiceUnavailableError):
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        if exc.status_code >= 500:
            report_error("api.error", "domain error surfaced", code=exc.code)
        return _error_response(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        if _is_invalid_timestamp(exc):
            return _error_response(
                400,
                "invalid_timestamp",
                "Timestamps must include an explicit UTC offset or Z; "
                "naive timestamps are rejected.",
            )
        details = [
            {"field": ".".join(str(loc) for loc in error.get("loc", [])), "issue": error.get("msg", "")}
            for error in exc.errors()
        ]
        return _error_response(422, "validation_failed", "Request validation failed.", {"fields": details})

    @app.exception_handler(FeatureUnavailableError)
    async def feature_unavailable_handler(request: Request, exc: FeatureUnavailableError):
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(ConfigurationError)
    async def configuration_error_handler(request: Request, exc: ConfigurationError):
        report_error("api.configuration_error", "configuration error", code=exc.code)
        return _error_response(500, exc.code, exc.message, exc.details)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        report_error("api.unhandled", "unhandled error", error=str(exc)[:300])
        return _error_response(500, "internal_error", "An unexpected failure occurred.")