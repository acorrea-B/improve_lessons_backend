"""Assistant service (T088, US-9).

The assistant opens threads, appends user messages, and returns a reply
generated through the ``ContentGenerator`` port, grounded in RAG-retrieved
history chunks (per-user isolation) and written with the user's preferred
name at their CEFR level. Educational content generated for delivery goes
through the content workflow (US-12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.entities.feature_availability import AuditEvent
from app.core.entities.materials import GenerationInputs
from app.core.entities.summary_chunk import AssistantThread, ThreadMessage
from app.core.errors import ForbiddenError, NotFoundError, ValidationErrorDetail
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.assistant_thread_repository import AssistantThreadRepository
from app.core.ports.content_generator import ContentGenerator
from app.core.ports.user_repository import UserRepository
from app.core.time.utc import now_utc
from app.utils.logging import get_logger, report_info

from app.services.rag_service import RAGService

if TYPE_CHECKING:
    from app.services.content.corrective_loop import CorrectiveLoop

logger = get_logger("services.assistant")

ASSISTANT_FEATURE = "assistant"


class AssistantService:
    def __init__(
        self,
        threads: AssistantThreadRepository,
        users: UserRepository,
        rag: RAGService,
        generator: ContentGenerator,
        features,
        audit_events: AuditEventRepository,
    ) -> None:
        self._threads = threads
        self._users = users
        self._rag = rag
        self._generator = generator
        self._features = features  # FeatureAvailabilityService
        self._audit = audit_events

    async def open_thread(self, owner_user_id: str) -> AssistantThread:
        await self._features.ensure_enabled(ASSISTANT_FEATURE)
        thread = AssistantThread(
            owner_user_id=owner_user_id,
            messages=[],
            updated_at=now_utc(),
        )
        await self._threads.insert(thread)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="assistant.thread_opened",
                payload={"thread_id": str(thread.id)},
            )
        )
        return thread

    async def list_threads(self, owner_user_id: str) -> list[AssistantThread]:
        return await self._threads.list_for_owner(owner_user_id)

    async def get_thread(self, owner_user_id: str, thread_id: str) -> AssistantThread:
        thread = await self._threads.get(thread_id, owner_user_id)
        if thread is None:
            raise NotFoundError(
                "thread_not_found", "No thread with that id for this user."
            )
        return thread

    async def delete_thread(self, owner_user_id: str, thread_id: str) -> None:
        thread = await self.get_thread(owner_user_id, thread_id)
        await self._threads.delete(thread_id, owner_user_id)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="assistant.thread_deleted",
                payload={"thread_id": str(thread.id)},
            )
        )

    async def message_thread(
        self, owner_user_id: str, thread_id: str, content: str
    ) -> tuple[AssistantThread, ThreadMessage]:
        """Append a user message and produce the assistant's reply.

        Cross-user access is rejected (403) by the caller-level ownership
        check in ``get_thread`` and re-checked here for defense in depth.
        """
        if not content or not content.strip():
            raise ValidationErrorDetail(
                code="empty_content", message="The message must not be empty.",
                details={"field": "content"},
            )
        await self._features.ensure_enabled(ASSISTANT_FEATURE)
        thread = await self._threads.get(thread_id, owner_user_id)
        if thread is None:
            raise NotFoundError(
                "thread_not_found", "No thread with that id for this user."
            )
        if thread.owner_user_id != owner_user_id:  # defense in depth
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=thread.owner_user_id,
                    event_type="assistant.cross_user_access_denied",
                    payload={"thread_id": thread_id},
                )
            )
            raise ForbiddenError(
                "forbidden", "The authenticated principal does not own this thread."
            )
        user_message = ThreadMessage(role="user", content=content.strip(), sent_at=now_utc())
        thread = await self._threads.append_message(
            thread_id, owner_user_id, user_message
        )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="assistant.message_appended",
                payload={"thread_id": thread_id},
            )
        )

        user = await self._users.get_by_id(owner_user_id)
        if user is None:
            raise NotFoundError("user_not_found", "No user for the authenticated principal.")
        context_texts, context_ids = await self._rag.retrieve(owner_user_id, content)
        from app.core.ports.content_generator import GeneratedContent

        inputs = GenerationInputs(
            cefr_level=user.cefr_level.value,
            purpose="assistant conversational reply",
            history_slice=context_texts,
            kind="conversational",
        )
        reply = await self._generator.generate(
            _assistant_instruction(user, content, context_texts), inputs
        )
        payload = reply.payload
        # The conversational envelope carries the reply under "reply"; the
        # "reading.body" fallback keeps the previous contract working
        # (the deterministic stub still answers with a reading body).
        reply_text = (
            payload.get("reply")
            or payload.get("reading", {}).get("body", "")
            or "I could not ground an answer in your documented history yet."
        )
        assistant_message = ThreadMessage(
            role="assistant", content=reply_text, sent_at=now_utc()
        )
        thread = await self._threads.append_message(
            thread_id, owner_user_id, assistant_message
        )
        if context_ids:
            merged = list(set(context_ids))
            thread = await self._threads.set_context_refs(
                thread_id, owner_user_id, merged
            )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=owner_user_id,
                event_type="assistant.turn_completed",
                payload={
                    "thread_id": thread_id,
                    "context_chunks": len(context_ids),
                    "cefr_level": user.cefr_level.value,
                },
            )
        )
        report_info(
            "assistant.turn_completed", "assistant replied",
            thread_id=thread_id, chunks=len(context_ids),
        )
        return thread, assistant_message


def _assistant_instruction(user, question: str, context_texts: list[str]) -> str:
    context = "\n".join(f"- {text}" for text in context_texts) or "- (no history yet)"
    name = user.preferred_name or user.name
    return (
        f"Address the learner as {name}. Reply strictly at CEFR level "
        f"{user.cefr_level.value}. Ground the reply in the documented "
        f"learning history below.\nHistory:\n{context}\n"
        f"Learner question: {question}"
    )