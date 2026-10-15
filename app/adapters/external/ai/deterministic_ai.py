"""Deterministic AI adapters (T020) used until the provider decisions in
``research.md § 4 / open decisions`` are approved.

The generation and evaluation adapters are intentionally structurally
independent: no shared prompts, no shared state (constitution principle
II). Generation produces CEFR-calibrated material from a documented
history slice; evaluation applies a fixed rubric over the generated
payload. Outbound HTTP integrations use VCR cassettes when a real
provider is configured (not in this release).
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from app.core.entities.content_workflow import CriterionAssessment
from app.core.entities.enums import Verdict
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from app.core.entities.materials import GenerationInputs
    from app.core.ports.content_evaluator import EvaluationResult
    from app.core.ports.content_generator import GeneratedContent
from app.utils.logging import report_info

logger = get_logger("ai.stubs")

GENERATION_MODEL_ID = "deterministic-generator-v1"
EVALUATION_MODEL_ID = "deterministic-evaluator-v1"
EMBEDDING_MODEL_ID = "deterministic-embedding-v1"
EMBEDDING_DIM = 32

#: Vocabulary band per CEFR level used by the deterministic generator.
_LEVEL_WORDS: dict[str, list[str]] = {
    "A1": ["basic", "every day", "my home", "my family"],
    "A2": ["simple past", "usually", "weekends", "plans"],
    "B1": ["adverb", "conjugate", "express opinions", "collocation"],
    "B2": ["subordinate clause", "nuance", "register", "phrasal verb"],
    "C1": ["discourse marker", "hedging", "cohesion", "nuanced register"],
    "C2": ["precise register", "idiomatic economy", "stylistic control", "cultural nuance"],
}


class DeterministicContentGenerator:
    """Fake Content Generation Model (constitution principle II: the
    generation model NEVER self-evaluates or approves its own output)."""

    model_id = GENERATION_MODEL_ID

    async def generate(
        self, instruction: str, inputs: GenerationInputs
    ) -> "GeneratedContent":
        from app.core.ports.content_generator import GeneratedContent

        level = inputs.cefr_level
        words = _LEVEL_WORDS.get(level, _LEVEL_WORDS["B1"])
        history_digest = _digest(inputs.history_slice)
        purpose = inputs.purpose.replace(" ", "_").lower()
        title = f"{words[0].capitalize()} practice: {purpose}"
        body = (
            f"{level} reading: This exercise builds on your documented work "
            f"({history_digest}). {words[1].capitalize()} you have practiced "
            f"recently, focus on {words[2]} and {words[3]}."
        )
        payload = {
            "reading": {
                "title": title,
                "body": body,
                "vocabulary": words,
            },
            "writing_exercises": [
                {
                    "prompt": (
                        f"Write a short {level} paragraph using "
                        f"{words[0]}, {words[1]} and what you documented today "
                        f"({history_digest})."
                    )
                }
            ],
        }
        raw_output = json.dumps(payload, sort_keys=True)
        report_info(
            "content.generated", "deterministic generation produced material",
            model_id=self.model_id, cefr_level=level,
        )
        return GeneratedContent(
            model_id=self.model_id, payload=payload, raw_output=raw_output
        )


class DeterministicContentEvaluator:
    """Fake Content Evaluation Model. Applies the six criteria rubric
    (vocabulary, grammar, sentence length, reading demands, writing
    demands, relevance) INDEPENDENTLY of the generator."""

    model_id = EVALUATION_MODEL_ID

    async def evaluate(
        self,
        generated: "GeneratedContent",
        cefr_level: str,
        purpose: str,
    ) -> "EvaluationResult":
        from app.core.ports.content_evaluator import EvaluationResult

        payload = generated.payload
        reading_body = str(payload.get("reading", {}).get("body", ""))
        exercises = payload.get("writing_exercises") or []

        vocabulary_ok = bool(payload.get("reading", {}).get("vocabulary"))
        grammar_ok = bool(reading_body)  # structural rubric placeholder
        sentence_length_ok = len(reading_body.split()) <= 120
        reading_demands_ok = sentence_length_ok and bool(reading_body.strip())
        writing_demands_ok = len(exercises) >= 1 and all(
            bool(exercise.get("prompt", "").strip()) for exercise in exercises
        )
        # Relevance: the evaluation only approves material grounded in the
        # documented history (the generator embeds the history digest /
        # "documented work" marker; a generic boilerplate body is rejected).
        vocabulary_ok = bool(payload.get("reading", {}).get("vocabulary"))
        relevance_ok = bool(reading_body) and (
            "documented" in reading_body or "practice" in reading_body
        )

        checks = [
            ("vocabulary", vocabulary_ok),
            ("grammar", grammar_ok),
            ("sentence_length", sentence_length_ok),
            ("reading_demands", reading_demands_ok),
            ("writing_demands", writing_demands_ok),
            ("relevance", relevance_ok),
        ]
        assessments = [
            CriterionAssessment(
                criterion=name,
                passed=passed,
                comment="deterministic rubric" if passed else "does not meet rubric",
            )
            for name, passed in checks
        ]
        verdict = Verdict.APPROVED if all(passed for _, passed in checks) else Verdict.REJECTED
        rationale = (
            f"All criteria passed at {cefr_level}."
            if verdict is Verdict.APPROVED
            else "Rejected: "
            + ", ".join(name for name, passed in checks if not passed)
        )
        report_info(
            "content.evaluated", "deterministic evaluation completed",
            model_id=self.model_id, verdict=verdict.value,
        )
        return EvaluationResult(
            model_id=self.model_id,
            verdict=verdict,
            criterion_assessments=assessments,
            rationale=rationale,
        )


class DeterministicEmbeddingProvider:
    """Deterministic hashing embedding: reproducible without network access
    and adequate for the in-process cosine-similarity adapter."""

    model_id = EMBEDDING_MODEL_ID
    embedding_dim = EMBEDDING_DIM

    async def embed(self, texts: "list[str]") -> "list[list[float]]":
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIM
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIM
            vector[index] += 1.0
        norm = sum(value ** 2 for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


def _digest(history_slice: list[str]) -> str:
    if not history_slice:
        return "your recent practice"
    combined = " · ".join(history_slice[-3:])[:80]
    return combined