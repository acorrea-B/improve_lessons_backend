"""Assistant endpoints (T089/090, US-9, contract § Personalized AI assistant)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.api.v1.dependencies.auth import get_current_user_id
from app.api.v1.requests import MessageRequest
from app.api.v1.responses import error_envelope, serialize, serialize_list

router = APIRouter(prefix="/users/me/assistant", tags=["assistant"])


@router.post("/threads", status_code=201)
async def open_thread(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    thread = await container.services.assistant.open_thread(user_id)
    return serialize(thread)


@router.get("/threads")
async def list_threads(request: Request, user_id: str = Depends(get_current_user_id)):
    container = request.app.state.container
    threads = await container.services.assistant.list_threads(user_id)
    return {"threads": serialize_list(threads)}


@router.get("/threads/{thread_id}")
async def get_thread(
    request: Request, thread_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    thread = await container.services.assistant.get_thread(user_id, thread_id)
    return serialize(thread)


@router.post("/threads/{thread_id}/messages")
async def post_message(
    request: Request,
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    # FR-065: the assistant is text-only; non-text payloads get 415. The
    # check precedes body validation so a binary payload is not parsed.
    content_type = request.headers.get("content-type", "")
    if content_type and "application/json" not in content_type:
        return JSONResponse(
            status_code=415,
            content=error_envelope(
                "unsupported_media_type",
                "The assistant accepts text-only messages (application/json).",
            ),
        )
    body = await request.body()
    try:
        parsed = MessageRequest.model_validate_json(body or b"{}")
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "validation_failed", "Request validation failed.",
                {"fields": [{"issue": str(error["msg"])} for error in exc.errors()]},
            ),
        )
    container = request.app.state.container
    thread, reply = await container.services.assistant.message_thread(
        user_id, thread_id, parsed.content
    )
    return {"thread": serialize(thread), "reply": serialize(reply)}


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    request: Request, thread_id: str, user_id: str = Depends(get_current_user_id)
):
    container = request.app.state.container
    await container.services.assistant.delete_thread(user_id, thread_id)
    return JSONResponse(status_code=204, content=None)