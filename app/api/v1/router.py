"""API v1 router (T025) — mounts every endpoint under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistant,
    auth,
    daily_materials,
    history,
    motivation,
    monthly_summaries,
    platforms,
    progress,
    summaries,
    system,
    users,
    weekly_summaries,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(platforms.router)
api_router.include_router(summaries.router)
api_router.include_router(daily_materials.router)
api_router.include_router(weekly_summaries.router)
api_router.include_router(monthly_summaries.router)
api_router.include_router(history.router)
api_router.include_router(assistant.router)
api_router.include_router(progress.router)
api_router.include_router(motivation.router)
api_router.include_router(system.router)