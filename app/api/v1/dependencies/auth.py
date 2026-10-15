"""Authentication + ownership dependencies (T035, FR-082/083)."""

from __future__ import annotations

from fastapi import Request

from app.core.errors import UnauthorizedError
from app.core.time.utc import require_aware_utc


async def get_container(request: Request):
    """Composition-root container built in ``main.py``."""
    return request.app.state.container


async def get_current_user_id(request: Request) -> str:
    """Resolve the authenticated principal (contract § Conventions).

    Tokens are the HMAC-signed values issued by /auth/register and
    /auth/login; logout invalidates previously issued tokens via
    ``users.session_valid_after`` (checked here with the token's
    ``issued_at``).
    """
    container = request.app.state.container
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise UnauthorizedError("unauthenticated", "Authentication is required.")
    token = header.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedError("unauthenticated", "Authentication is required.")
    from datetime import UTC, datetime

    context = await container.authenticator.authenticate(token)
    if context is None:
        raise UnauthorizedError(
            "invalid_token", "The session token is invalid or expired."
        )
    user = await container.services.users.get_me(context.user_id)
    if user is not None and user.session_valid_after is not None:
        revoked_after = require_aware_utc(user.session_valid_after)
        if context.issued_at < revoked_after:
            raise UnauthorizedError(
                "invalid_token", "The session token has been revoked."
            )
    return context.user_id


def owner_of(resource_owner: str, principal: str) -> None:
    """Object-level access control (FR-082/083): cross-user access → 403."""
    from app.core.errors import ForbiddenError

    if resource_owner != principal:
        raise ForbiddenError(
            "forbidden", "The authenticated principal does not own this resource."
        )