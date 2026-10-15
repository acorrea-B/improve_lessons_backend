"""Users endpoints (US-1, contract § Users)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.endpoints.auth import user_response
from app.api.v1.requests import UpdateProfileRequest

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("")
async def get_me(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    return user_response(user)


@router.patch("")
async def update_me(
    request: Request,
    payload: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
):
    container = request.app.state.container
    changes = {
        field: value
        for field, value in payload.model_dump().items()
        if value is not None
    }
    user = await container.services.users.update_me(user_id, changes)
    return user_response(user)