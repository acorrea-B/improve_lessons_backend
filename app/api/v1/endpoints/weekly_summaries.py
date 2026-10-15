"""Weekly + monthly summaries endpoints (T071/T077, US-6, US-7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.dependencies.range import parse_date_range
from app.api.v1.responses import error_envelope, serialize, serialize_list

router = APIRouter(prefix="/users/me", tags=["weekly"])


@router.get("/weekly-summaries")
async def list_weekly_summaries(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    await container.services.feature_availability.ensure_enabled("weekly_summaries")
    start, end = parse_date_range(from_date, to_date, user.time_zone)
    summaries = await container.services.weekly_rollup.compute_range(user_id, start, end)
    return {"weekly_summaries": serialize_list(summaries)}


@router.get("/weekly-summaries/{weekly_summary_id}")
async def get_weekly_summary(
    request: Request, weekly_summary_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    summary = await container.services.weekly_rollup.get_or_404(user_id, weekly_summary_id)
    return serialize(summary)


@router.get("/weekly-summaries/{weekly_summary_id}/material")
async def get_weekly_material(
    request: Request, weekly_summary_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    summary = await container.services.weekly_rollup.get_or_404(user_id, weekly_summary_id)
    material = await container.services.weekly_materials.get_by_weekly_summary(
        str(summary.id), user_id
    )
    if material is None or material.approved_at is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope("material_not_found", "No approved weekly material for this period."),
        )
    return serialize(material)
