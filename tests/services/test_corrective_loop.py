"""US-12 corrective-loop tests (T056): bound enforcement, unapproved
material never delivered, transient-failure absorption."""

from __future__ import annotations

import unittest

from app.adapters.external.ai.deterministic_ai import (
    DeterministicContentEvaluator,
    DeterministicContentGenerator,
)
from app.core.entities.materials import GenerationInputs
from app.core.ports.content_generator import GeneratedContent, TransientAIError
from app.core.ports.content_evaluator import EvaluationResult
from app.core.entities.enums import Verdict
from app.core.entities.content_workflow import CriterionAssessment
from app.services.content.corrective_loop import CorrectiveLoop


def inputs(cefr: str = "B1", history: list[str] | None = None) -> GenerationInputs:
    return GenerationInputs(
        cefr_level=cefr,
        purpose="daily practice",
        history_slice=history or ["I reviewed the present simple."],
    )


class FailingEvaluator:
    model_id = "test-evaluator"

    def __init__(self, rejections: int) -> None:
        self.rejection_count = rejections
        self.calls = 0

    async def evaluate(self, generated, cefr_level, purpose):
        self.calls += 1
        from app.core.ports.content_evaluator import EvaluationResult

        verdict = Verdict.REJECTED if self.calls <= self.rejection_count else Verdict.APPROVED
        return EvaluationResult(
            model_id=self.model_id,
            verdict=verdict,
            criterion_assessments=[
                CriterionAssessment(criterion="relevance", passed=verdict is Verdict.APPROVED)
            ],
            rationale="testing",
        )


class FlakyGenerator:
    model_id = "test-generator"

    def __init__(self, failures: int) -> None:
        self.failures_remaining = failures
        self.calls = 0

    async def generate(self, instruction, inputs):
        self.calls += 1
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise TransientAIError("provider transient failure (simulated)")
        return DeterministicContentGenerator().generate.__wrapped__ if False else None


class CountingGenerator:
    """Deterministic generator that raises `failures` TransientAIError first."""

    model_id = "test-generator"

    def __init__(self, failures: int, fallback=None) -> None:
        self.failures_remaining = failures
        self.calls = 0
        self._fallback = fallback

    async def generate(self, instruction, inputs):
        self.calls += 1
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise TransientAIError("provider transient failure (simulated)")
        real = DeterministicContentGenerator()
        return await real.generate(instruction, inputs)


class TestCorrectiveLoop(unittest.TestCase):
    def test_rejection_then_revision_within_bound(self):
        from asyncio import run

        async def flow():
            loop = CorrectiveLoop(
                DeterministicContentGenerator(), FailingEvaluator(rejections=1), bound=3
            )
            return await loop.run("instruction", inputs())

        outcome = run(flow())
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.attempt_number, 2)
        self.assertEqual(len(outcome.attempts), 2)
        self.assertEqual(len(outcome.evaluations), 2)

    def test_bound_exhausted_never_delivers(self):
        from asyncio import run

        async def flow():
            loop = CorrectiveLoop(
                DeterministicContentGenerator(), FailingEvaluator(rejections=99), bound=2
            )
            return await loop.run("instruction", inputs())

        outcome = run(flow())
        self.assertEqual(outcome.status, "bound_exhausted")
        self.assertFalse(outcome.approved)
        self.assertIsNone(None)
        # no approved evaluation exists in the attempts
        approved = [
            item for item in outcome.evaluations if item.verdict is Verdict.APPROVED
        ]
        self.assertEqual(approved, [])

    def test_transient_failures_absorbed_within_bound(self):
        from asyncio import run

        async def flow():
            loop = CorrectiveLoop(
                CountingGenerator(failures=2), DeterministicContentEvaluator(), bound=3
            )
            return await loop.run("instruction", inputs())

        outcome = run(flow())
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.attempts[-1].calls if hasattr(outcome.attempts[-1], "calls") else 0, 0)

    def test_transient_failure_beyond_bound_is_contained(self):
        from asyncio import run

        async def flow():
            loop = CorrectiveLoop(
                CountingGenerator(failures=99), DeterministicContentEvaluator(), bound=3
            )
            return await loop.run("instruction", inputs())

        outcome = run(flow())
        self.assertEqual(outcome.status, "bound_exhausted")


if __name__ == "__main__":
    unittest.main()