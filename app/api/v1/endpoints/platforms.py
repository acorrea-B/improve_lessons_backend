"""Platform + schedule + session endpoints (T041, US-2, FR-009–FR-014)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.dependencies.range import parse_date_range
from app.api.v1.requests import PlatformCreateRequest, ScheduleCreateRequest, ScheduleUpdateRequest
from app.api.v1.responses import serialize, serialize_list

router = APIRouter(prefix="/users/me", tags=["platforms", "schedules", "sessions"])


@router.get("/platforms")
async def list_platforms(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    platforms = await container.services.platforms.list(user_id)
    return {"platforms": serialize_list(platforms)}


@router.post("/platforms", status_code=201)
async def create_platform(
    request: Request,
    payload: PlatformCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    container = request.app.state.container
    platform = await container.services.platforms.register(user_id, payload.name, payload.url)
    return serialize(platform)


@router.delete("/platforms/{platform_id}", status_code=204)
async def delete_platform(
    request: Request, platform_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    await container.services.platforms.remove(user_id, platform_id)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=204, content=None)


@router.get("/schedules")
async def list_schedules(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    schedules = await container.services.schedules.list(user_id)
    return {"schedules": serialize_list(schedules)}


@router.post("/schedules", status_code=201)
async def create_schedule(
    request: Request,
    payload: ScheduleCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    container = request.app.state.container
    schedule = await container.services.schedules.create(user_id, payload.model_dump())
    return serialize(schedule)


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    request: Request, schedule_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    schedule = await container.services.schedules.get(user_id, schedule_id)
    return serialize(schedule)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    request: Request,
    schedule_id: str,
    payload: ScheduleUpdateRequest,
    user_id: str = Depends(get_current_user_id),
):
    container = request.app.state.container
    from app.core.entities.feature_availability import AuditEvent

    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    schedule = await container.services.schedules.update(user_id, schedule_id, changes)
    await container.services.audit_events.insert(
        AuditEvent(
            owner_user_id=user_id,
            event_type="schedule.updated",
            payload={"schedule_id": schedule_id},
        )
    )
    return serialize(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    request: Request, schedule_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    await container.services.schedules.delete(user_id, schedule_id)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=204, content=None)


@router.get("/sessions")
async def list_sessions(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    start, end = parse_date_range(from_date, to_date, user.time_zone)
    sessions = await container.services.sessions_repo.list_for_owner(
        user_id, from_instant=start, to_instant=end
    )
    return {"sessions": serialize_list(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(
    request: Request, session_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    from app.core.errors import NotFoundError

    session = await container.services.sessions_repo.get(session_id, user_id)
    if session is None:
        raise NotFoundError("session_not_found", "No session with that id for this user.")
    return serialize(session)