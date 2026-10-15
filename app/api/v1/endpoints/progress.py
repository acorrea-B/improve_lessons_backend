"""Progress endpoints (T094, US-10, contract § Progress indicators)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.responses import serialize

router = APIRouter(prefix="/users/me/progress", tags=["progress"])


@router.get("")
async def get_progress(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    await container.services.feature_availability.ensure_enabled("progress")
    report = await container.services.progress.report(user_id)
    await container.services.audit_events.insert(
        __audit(user_id, "progress.requested")
    )
    return report


@router.get("/streaks")
async def get_streaks(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    streaks = await container.services.progress.streaks(user_id)
    await container.services.audit_events.insert(
        __audit(user_id, "streaks.requested")
    )
    return streaks


def __audit(user_id: str, event_type: str):
    from app.core.entities.feature_availability import AuditEvent
    from app.utils.logging import report_info

    report_info(event_type.replace(".", "_"), "progress fetch", user_id=user_id)
    return AuditEvent(owner_user_id=user_id, event_type=event_type, payload={})