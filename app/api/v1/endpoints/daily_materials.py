"""Daily material endpoints (T065, US-5, contract § Daily materials)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.dependencies.range import parse_date_range
from app.api.v1.responses import error_envelope, serialize, serialize_list

router = APIRouter(prefix="/users/me", tags=["daily-materials"])


@router.get("/summaries/{summary_id}/material")
async def get_material_by_summary(
    request: Request, summary_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("daily_materials")
    material = await container.services.daily_materials.get_by_summary(user_id, summary_id)
    if material is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                "material_not_found",
                "No approved material for this summary yet (FR-042).",
            ),
        )
    return serialize(material)


@router.get("/sessions/{session_id}/summary/material")
async def get_material_by_session(
    request: Request, session_id: str, user_id: str = Depends(get_current_user_id)
):
    """Fetch-or-produce the approved material for the session's summary.

    Approval goes through the content workflow (US-12); an already
    approved material is served from cache with no new corrective-loop run
    (FR-046). 404 when no approved material exists yet (FR-042).
    """
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("daily_materials")
    user = await container.services.users.get_me(user_id)
    summary = await container.services.summaries.get_by_session(user_id, session_id)
    material = (
        await container.services.daily_materials.request_material(
            user_id, summary, cefr_level=user.cefr_level.value
        )
        if summary is not None
        else None
    )
    if material is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                "material_not_found",
                "No approved material for this summary yet (FR-042).",
            ),
        )
    return serialize(material)


@router.get("/daily-materials")
async def list_daily_materials(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    start, end = parse_date_range(from_date, to_date, user.time_zone)
    materials = await container.services.daily_materials.list_in_range(user_id, start, end)
    return {"materials": serialize_list(materials)}