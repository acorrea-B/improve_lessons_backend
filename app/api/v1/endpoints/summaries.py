"""Daily summary endpoints (T053, US-4, contract § Daily summaries)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.dependencies.range import parse_date_range
from app.api.v1.requests import SummaryCreateRequest
from app.api.v1.responses import serialize, serialize_list

router = APIRouter(prefix="/users/me", tags=["summaries"])


@router.post("/sessions/{session_id}/summary", status_code=201)
async def submit_summary(
    request: Request,
    session_id: str,
    payload: SummaryCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    summary = await container.services.summaries.submit(
        user_id, session_id, payload.content, user_time_zone=user.time_zone
    )
    # RAG pipeline: chunk + embed + index the summary (US-9 groundwork,
    # T087). Failure is contained — the summary stays persisted either way.
    try:
        await container.services.rag.ingest(summary)
    except Exception as exc:
        from app.utils.logging import report_error

        report_error(
            "rag.ingest_failed", "summary chunk indexing failed (contained)",
            summary_id=str(summary.id), error=str(exc)[:200],
        )
    return serialize(summary)


@router.get("/summaries/{summary_id}")
async def get_summary(
    request: Request, summary_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    summary = await container.services.summaries.get(user_id, summary_id)
    return serialize(summary)


@router.get("/summaries")
async def list_summaries(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    container = request.app.state.container
    user = await container.services.users.get_me(user_id)
    start, end = parse_date_range(from_date, to_date, user.time_zone)
    summaries = await container.services.summaries.list_in_range(user_id, start, end)
    return {"summaries": serialize_list(summaries)}