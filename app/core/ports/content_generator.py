"""ContentGenerator port (T014, constitution principle II).

The generation model's contract: produce material for the requested
purpose, NEVER self-evaluate or approve its own output. The
``ContentEvaluationModel`` is a separate port (``content_evaluator``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.core.ports.ai_errors import TransientAIError

if TYPE_CHECKING:
    from app.core.entities.materials import GenerationInputs

__all__ = [
    "ContentGenerator",
    "GeneratedContent",
    "TransientAIError",
]


class GeneratedContent:
    """Raw structured output of a Content Generation Model."""

    def __init__(self, model_id: str, payload: dict, raw_output: str) -> None:
        self.model_id = model_id
        self.payload = payload
        self.raw_output = raw_output


class ContentGenerator(ABC):
    model_id: str

    @abstractmethod
    async def generate(
        self, instruction: str, inputs: "GenerationInputs"
    ) -> "GeneratedContent":
        """Produce material for the requested purpose; NEVER self-evaluates."""
        ...