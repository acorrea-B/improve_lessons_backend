"""Motivation + challenges endpoints (T100/T101, US-11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.responses import serialize

router = APIRouter(prefix="/users/me", tags=["motivation", "challenges"])


@router.get("/recognitions")
async def get_recognitions(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("recognitions")
    recognitions = await container.services.motivation.recognitions(user_id)
    return {"recognitions": serialize(recognitions)}


@router.get("/challenges")
async def get_next_challenge(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("challenges")
    challenge = await container.services.motivation.next_challenge(user_id)
    return serialize(challenge)


@router.post("/challenges/{challenge_id}/start")
async def start_challenge(
    request: Request, challenge_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("challenges")
    challenge = await container.services.motivation.start_challenge(user_id, challenge_id)
    return serialize(challenge)