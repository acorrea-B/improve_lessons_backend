"""Idempotency middleware (T030, contract § Conventions, FR-046 support).

For any POST/PATCH/DELETE carrying an ``Idempotency-Key`` header:
- a known key replays the original response verbatim,
- an unknown key acquires a short-lived lease (a pending record with a
  uniqueness constraint on (owner, key, method, path) so two concurrent
  requests with the same key cannot both reach the service), forwards the
  request, then stores the final response.
Records expire per the TTL in ``data-model.md`` § Conventions.
"""

from __future__ import annotations

import json
from datetime import timedelta

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.entities.feature_availability import IdempotencyRecord
from app.core.errors import UnauthorizedError
from app.core.time.utc import now_utc
from app.utils.logging import get_logger, report_info

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
LEASE_TTL = timedelta(days=1)

logger = get_logger("api.idempotency")


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method not in WRITE_METHODS:
            return await call_next(request)
        key = request.headers.get("idempotency-key")
        if not key:
            return await call_next(request)

        container = request.app.state.container
        store = container.services.idempotency_store
        try:
            user_id = await container.resolve_current_user_id(request)
        except UnauthorizedError:
            return await call_next(request)  # auth errors surface normally

        scope = {
            "owner_user_id": user_id,
            "idempotency_key": key,
            "method": request.method,
            "path": request.url.path,
        }
        existing = await store.find(**scope)
        if existing is not None:
            if existing.status_code and existing.response_body:
                report_info(
                    "idempotency.replayed", "idempotent replay",
                    path=scope["path"], key=key,
                )
                return Response(
                    content=existing.response_body,
                    status_code=existing.status_code,
                    media_type="application/json",
                )
            # In-flight lease held by a concurrent duplicate request.
            return Response(
                content=json.dumps(
                    {"error": {"code": "idempotency_in_flight",
                               "message": "An identical request is still in flight."}}
                ),
                status_code=503,
                headers={"Retry-After": "1"},
                media_type="application/json",
            )

        acquired = await store.insert(
            IdempotencyRecord(
                owner_user_id=user_id,
                idempotency_key=key,
                method=request.method,
                path=request.url.path,
                status_code=0,
                response_body="",
                expires_at=now_utc() + LEASE_TTL,
            )
        )
        if not acquired:
            return Response(
                content=json.dumps(
                    {"error": {"code": "idempotency_in_flight",
                               "message": "An identical request is still in flight."}}
                ),
                status_code=503,
                headers={"Retry-After": "1"},
                media_type="application/json",
            )

        response = await call_next(request)
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk
        try:
            response_body = body_bytes.decode()
        except UnicodeDecodeError:
            response_body = ""
        await store.update_response(
            user_id, key, request.method, request.url.path,
            status_code=response.status_code, response_body=response_body,
        )
        rebuilt_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in ("content-length",)
        }
        rebuilt = Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=rebuilt_headers,
            media_type=response.media_type,
        )
        return rebuilt