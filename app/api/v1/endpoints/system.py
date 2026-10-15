"""System endpoints (T106, US-13, contract § Feature availability)."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/system/features")
async def list_features(request: Request):
    """Public; no authentication required (contract § Feature availability)."""
    container = request.app.state.container
    state = await container.services.feature_availability.list_state()
    overrides_note = (
        "Per-user overrides are a forward concern (FR-081); the initial "
        "release exposes the global on/off switch only."
    )
    return {"features": state, "overrides": overrides_note}


@router.get("/system/health")
async def health(request: Request):
    """Public health check: 200 with {"status": "ok"} when ready."""
    return {"status": "ok"}