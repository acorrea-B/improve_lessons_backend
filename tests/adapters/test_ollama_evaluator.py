"""Ollama content-evaluation adapter tests (T119).

Covers the six-criteria rubric, the FAIL-CLOSED verdict (anything short
of a complete all-green assessment is a rejection) and the isolation
between the two roles (constitution principle II: no shared prompts, no
shared internal state).
"""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.ai.ollama_client import OllamaClient
from app.adapters.external.ai.ollama_evaluator import (
    EVALUATION_SYSTEM_PROMPT,
    OllamaContentEvaluator,
)
from app.adapters.external.ai.ollama_generator import (
    GENERATION_SYSTEM_PROMPT,
    OllamaContentGenerator,
)
from app.core.entities.enums import Verdict
from app.core.entities.materials import GenerationInputs
from app.core.ports.ai_errors import TransientAIError
from app.core.ports.content_generator import GeneratedContent
from tests.commons.vcr_config import make_vcr

BASE_URL = "http://ollama.test:11434"

ALL_CRITERIA = (
    "vocabulary",
    "grammar",
    "sentence_length",
    "reading_demands",
    "writing_demands",
    "relevance",
)


class RecordingClient(OllamaClient):
    """Client that records the request and returns a canned answer."""

    def __init__(self, content: str) -> None:
        super().__init__(BASE_URL)
        self.content = content
        self.requests: list = []

    async def chat(self, request):
        from app.adapters.external.ai.ollama_client import OllamaChatResponse

        self.requests.append(request)
        return OllamaChatResponse(
            content=self.content,
            model=request.model,
            done_reason="stop",
            eval_count=10,
            prompt_eval_count=20,
        )


def answer(verdict: str = "approved", *, failed: tuple[str, ...] = (), omit: tuple[str, ...] = ()) -> str:
    """Build an evaluation answer JSON string."""
    import json

    criteria = [
        {
            "criterion": name,
            "passed": name not in failed,
            "comment": f"{name} comment",
        }
        for name in ALL_CRITERIA
        if name not in omit
    ]
    return json.dumps(
        {
            "verdict": verdict,
            "rationale": "assessed against the six criteria",
            "criteria": criteria,
        }
    )


def generated() -> GeneratedContent:
    return GeneratedContent(
        model_id="minimax-m3.1-flash:cloud",
        payload={
            "reading": {
                "title": "A Morning Routine",
                "body": "Every weekday, Ana wakes up at seven o'clock.",
                "vocabulary": ["routine", "weekday"],
            },
            "writing_exercises": [{"prompt": "Write five sentences."}],
        },
        raw_output="{}",
    )


class TestOllamaContentEvaluator(unittest.TestCase):
    def test_approves_only_with_the_six_criteria_passing(self):
        client = RecordingClient(answer())
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        result = run(evaluator.evaluate(generated(), "B1", "daily practice"))

        self.assertEqual(result.model_id, "glm-5.3-flash:cloud")
        self.assertIs(result.verdict, Verdict.APPROVED)
        self.assertEqual(len(result.criterion_assessments), 6)
        self.assertTrue(all(item.passed for item in result.criterion_assessments))
        self.assertEqual(
            [item.criterion for item in result.criterion_assessments], list(ALL_CRITERIA)
        )

    def test_rejects_when_a_criterion_fails(self):
        client = RecordingClient(answer("approved", failed=("relevance",)))
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        result = run(evaluator.evaluate(generated(), "B1", "daily practice"))

        self.assertIs(result.verdict, Verdict.REJECTED)
        self.assertIn("relevance", result.rationale)

    def test_rejects_when_the_model_itself_rejects(self):
        client = RecordingClient(answer("rejected", failed=("grammar",)))
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        result = run(evaluator.evaluate(generated(), "B1", "daily practice"))

        self.assertIs(result.verdict, Verdict.REJECTED)
        self.assertIn("did not approve", result.rationale)

    def test_fails_closed_when_a_criterion_is_missing(self):
        client = RecordingClient(answer("approved", omit=("grammar",)))
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        result = run(evaluator.evaluate(generated(), "B1", "daily practice"))

        self.assertIs(result.verdict, Verdict.REJECTED)
        self.assertIn("missing criteria", result.rationale)
        self.assertIn("grammar", result.rationale)

    def test_fails_closed_on_an_unparseable_answer(self):
        client = RecordingClient("the material looks fine to me")
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        with self.assertRaises(TransientAIError):
            run(evaluator.evaluate(generated(), "B1", "daily practice"))

    def test_sends_the_material_and_the_level(self):
        client = RecordingClient(answer())
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")

        run(evaluator.evaluate(generated(), "B1", "daily practice"))

        request = client.requests[0]
        self.assertEqual(request.model, "glm-5.3-flash:cloud")
        self.assertTrue(request.messages[0]["content"].startswith(EVALUATION_SYSTEM_PROMPT))
        self.assertIn("B1", request.messages[1]["content"])
        self.assertIn("A Morning Routine", request.messages[1]["content"])

    def test_evaluation_prompt_never_rewrites_the_material(self):
        prompt = EVALUATION_SYSTEM_PROMPT.lower()
        self.assertIn("never rewrite", prompt)
        self.assertIn("examiner", prompt)


class TestRoleIsolation(unittest.TestCase):
    """Constitution principle II: the two roles share no prompt and no state."""

    def test_the_two_roles_have_different_prompts(self):
        self.assertNotEqual(GENERATION_SYSTEM_PROMPT, EVALUATION_SYSTEM_PROMPT)
        self.assertNotIn("CEFR examiner", GENERATION_SYSTEM_PROMPT)
        self.assertNotIn("native English teacher", EVALUATION_SYSTEM_PROMPT)

    def test_the_two_adapters_share_no_internal_state(self):
        generator_client = RecordingClient("{}")
        evaluator_client = RecordingClient("{}")
        generator = OllamaContentGenerator(generator_client, model="model-a")
        evaluator = OllamaContentEvaluator(evaluator_client, model="model-b")

        self.assertIsNot(generator._client, evaluator._client)
        self.assertNotEqual(generator.model_id, evaluator.model_id)
        self.assertNotEqual(generator._max_tokens, evaluator._max_tokens)


class TestOllamaContentEvaluatorWithCassette(unittest.TestCase):
    """Replays a recorded provider exchange — no network access."""

    def test_replays_the_recorded_evaluation(self):
        vcr = make_vcr("ollama_evaluation.yaml")
        client = OllamaClient("http://ollama.test:11434", timeout_seconds=42)
        evaluator = OllamaContentEvaluator(client, model="glm-5.3-flash:cloud")
        with vcr.use_cassette("ollama_evaluation.yaml"):
            result = run(evaluator.evaluate(generated(), "B1", "daily practice"))
        self.assertIn(result.verdict, (Verdict.APPROVED, Verdict.REJECTED))
        self.assertEqual(len(result.criterion_assessments), 6)


class TestGenerationInputsKind(unittest.TestCase):
    def test_kind_defaults_to_material(self):
        self.assertEqual(GenerationInputs(cefr_level="B1", purpose="p").kind, "material")

    def test_kind_is_recorded_in_the_inputs(self):
        self.assertEqual(
            GenerationInputs(cefr_level="B1", purpose="p", kind="conversational").kind,
            "conversational",
        )


if __name__ == "__main__":
    unittest.main()
