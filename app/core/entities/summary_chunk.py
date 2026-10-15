"""Assistant thread + summary chunk entities (US-9, data-model.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.base import Entity
from app.core.entities.enums import MessageRole
from app.core.time.utc import AwareDatetime


class ThreadMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: MessageRole
    content: str  # text-only (FR-065)
    sent_at: AwareDatetime


class AssistantThread(Entity):
    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str
    messages: list[ThreadMessage] = Field(default_factory=list)
    retrieved_context_refs: list[str] = Field(default_factory=list)
    updated_at: AwareDatetime


class SummaryChunk(Entity):
    """Derived chunk of a daily summary for vector retrieval (US-9)."""

    model_config = ConfigDict(validate_assignment=True)

    owner_user_id: str  # per-user isolation in retrieval
    summary_id: str
    summary_content_version: int
    chunk_index: int
    text: str
    token_count: int
    embedding_model_id: str
    embedding: list[float]
    embedding_dim: int
    is_obsolete: bool = False