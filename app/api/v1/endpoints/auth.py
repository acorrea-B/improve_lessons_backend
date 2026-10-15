"""Authentication endpoints (T035, US-1, contract § Authentication)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.requests import LoginRequest, RegisterRequest
from app.api.v1.responses import serialize
from app.core.errors import UnauthorizedError, ValidationErrorDetail

router = APIRouter(tags=["auth"])


def user_response(user) -> dict:
    data = serialize(user)
    # Never leak authentication plumbing or internal versioning.
    for field in ("password_hash", "session_valid_after", "version", "created_at"):
        data.pop(field, None)
    data["id"] = data.get("id")
    return data


@router.post("/auth/register", status_code=201)
async def register(request: Request, payload: RegisterRequest):
    container = request.app.state.container
    user = await container.services.users.register(
        name=payload.name,
        email=payload.email,
        cefr_level=payload.cefr_level,
        time_zone=payload.time_zone,
        password=payload.password,
    )
    token = await container.authenticator.issue_token(str(user.id))
    return {"user": user_response(user), "token": token}


@router.post("/auth/login")
async def login(request: Request, payload: LoginRequest):
    container = request.app.state.container
    user = await container.services.users.verify_login(payload.email, payload.password)
    token = await container.authenticator.issue_token(str(user.id))
    return {"user": user_response(user), "token": token}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    await container.services.users.record_logout(user_id)
    return JSONResponse(status_code=204, content=None)


@router.get("/auth/me")
async def auth_me(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    return user_response(user)