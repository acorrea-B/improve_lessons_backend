"""History endpoints (T082, US-8, contract § Learning history)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.dependencies.range import parse_date_range
from app.api.v1.responses import serialize

router = APIRouter(prefix="/users/me/history", tags=["history"])


@router.get("")
async def list_history(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    start, end = parse_date_range(from_date, to_date, user.time_zone)
    view = await container.services.history.range(user_id, start, end)
    await container.services.audit_events.insert(
        __audit(user_id, "history.range_requested", {"from": str(from_date), "to": str(to_date)})
    )
    return {
        "summaries": serialize(list(view["summaries"])),
        "daily_materials": serialize(list(view["daily_materials"])),
        "weekly_summaries": serialize(list(view["weekly_summaries"])),
        "monthly_summaries": serialize(list(view["monthly_summaries"])),
    }


def __audit(user_id: str, event_type: str, payload: dict):
    from app.core.entities.feature_availability import AuditEvent

    return AuditEvent(owner_user_id=user_id, event_type=event_type, payload=payload)


@router.get("/days/{calendar_day}")
async def day_history(
    request: Request, calendar_day: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    view = await container.services.history.day(user_id, calendar_day)
    await container.services.audit_events.insert(
        __audit(user_id, "history.day_requested", {"day": calendar_day})
    )
    return view


@router.get("/weeks/{calendar_day}")
async def week_history(
    request: Request, calendar_day: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    view = await container.services.history.week(user_id, calendar_day)
    await container.services.audit_events.insert(
        __audit(user_id, "history.week_requested", {"week_of": calendar_day})
    )
    return view


@router.get("/months/{calendar_month}")
async def month_history(
    request: Request, calendar_month: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    view = await container.services.history.month(user_id, calendar_month)
    await container.services.audit_events.insert(
        __audit(user_id, "history.month_requested", {"month": calendar_month})
    )
    return view