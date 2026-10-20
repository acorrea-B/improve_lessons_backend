"""Wire schemas and JSON contracts for the Ollama AI adapters (US-12).

This module holds the SHARED *format* only: the pydantic models that
describe the JSON the provider must return, and the schema snippets that
are embedded in each role's prompt.

It deliberately does NOT hold the role prompts: constitution principle II
requires the generation model and the evaluation model to have NO shared
prompts, so each adapter owns its own system prompt (``ollama_generator``
and ``ollama_evaluator``). Nothing in this module is stateful either, so
the two roles share no internal state.

The provider may ignore ``format: <schema>`` (measured against
``minimax-m3.1-flash:cloud`` and ``glm-5.3-flash:cloud``: both return
prose when a JSON schema is supplied), so the schema is ALSO written
into the prompt and the answer is validated locally with pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: The six criteria the content evaluation model applies (FR-040).
CRITERIA: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "sentence_length",
    "reading_demands",
    "writing_demands",
    "relevance",
)


class ReadingSchema(BaseModel):
    """The reading part of the material envelope."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    vocabulary: list[str] = Field(default_factory=list)


class WritingExerciseSchema(BaseModel):
    """One writing exercise of the material envelope."""

    model_config = ConfigDict(extra="forbid")

    prompt: str


class MaterialPayloadSchema(BaseModel):
    """The ``payload`` of a generated curricular material."""

    model_config = ConfigDict(extra="forbid")

    reading: ReadingSchema
    writing_exercises: list[WritingExerciseSchema] = Field(min_length=1)


class ConversationalPayloadSchema(BaseModel):
    """The ``payload`` of a generated assistant reply."""

    model_config = ConfigDict(extra="forbid")

    reply: str


class CriterionSchema(BaseModel):
    """One criterion assessment inside the evaluation answer."""

    model_config = ConfigDict(extra="forbid")

    criterion: str
    passed: bool
    comment: str = ""


class EvaluationAnswerSchema(BaseModel):
    """The evaluation model's answer: a verdict plus the six criteria."""

    model_config = ConfigDict(extra="forbid")

    verdict: str
    rationale: str = ""
    criteria: list[CriterionSchema] = Field(default_factory=list)


#: Schema description embedded in the GENERATION prompt.
MATERIAL_SCHEMA_PROMPT = """{
  "reading": {
    "title": "<short title>",
    "body": "<the reading passage>",
    "vocabulary": ["<word or phrase>", "..."]
  },
  "writing_exercises": [
    {"prompt": "<instruction for the learner>"}
  ]
}"""

#: Schema description embedded in the CONVERSATIONAL generation prompt.
CONVERSATIONAL_SCHEMA_PROMPT = """{
  "reply": "<the assistant's reply to the learner>"
}"""

#: Schema description embedded in the EVALUATION prompt.
EVALUATION_SCHEMA_PROMPT = """{
  "verdict": "approved | rejected",
  "rationale": "<one short paragraph explaining the verdict>",
  "criteria": [
    {"criterion": "vocabulary", "passed": true, "comment": "<short comment>"},
    {"criterion": "grammar", "passed": true, "comment": "<short comment>"},
    {"criterion": "sentence_length", "passed": true, "comment": "<short comment>"},
    {"criterion": "reading_demands", "passed": true, "comment": "<short comment>"},
    {"criterion": "writing_demands", "passed": true, "comment": "<short comment>"},
    {"criterion": "relevance", "passed": true, "comment": "<short comment>"}
  ]
}"""
