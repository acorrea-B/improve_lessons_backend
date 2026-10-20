"""Ollama Content Evaluation Model (T119, US-12, constitution principle II).

The role is a **strict CEFR examiner**: it applies the six criteria of
FR-040 to the material a DIFFERENT model produced and returns a verdict.
It never rewrites or repairs the material — the generator corrects, the
evaluator only judges.

The verdict is fail-closed. ``APPROVED`` requires ALL of:
  1. the model said ``approved``;
  2. the six criteria are all present in the answer;
  3. every one of them passed.

Anything else (partial progress, a missing criterion, an unparseable
answer) is ``REJECTED`` with the reason logged. The six criteria are
therefore structurally guaranteed (FR-040) instead of depending on the
model's obedience.

The system prompt of this adapter is owned here and is NOT shared with
the generation adapter (principle II: no shared prompts, no shared
internal state). The two adapters never share a client instance either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.adapters.external.ai.ollama_client import (
    OllamaChatRequest,
    OllamaClient,
    extract_json_object,
)
from app.adapters.external.ai.ollama_schemas import (
    CRITERIA,
    EVALUATION_SCHEMA_PROMPT,
    EvaluationAnswerSchema,
)
from app.core.entities.content_workflow import CriterionAssessment
from app.core.entities.enums import Verdict
from app.core.ports.ai_errors import TransientAIError
from app.core.ports.content_evaluator import ContentEvaluator, EvaluationResult
from app.utils.logging import report_info

if TYPE_CHECKING:
    from app.core.ports.content_generator import GeneratedContent

#: The evaluation role. Owned by this module alone (constitution II).
EVALUATION_SYSTEM_PROMPT = """You are a strict CEFR examiner assessing English-learning \
material produced by another teacher. You are an examiner, not an editor.

You assess the material against exactly these six criteria:
1. vocabulary — the lexis matches the target CEFR level: it uses what that level \
owns and does not stay below it. A1-A2 lexis for a B1 learner fails this criterion.
2. grammar — the grammar is correct and at the target level.
3. sentence_length — the sentences are of a length a learner at that level can read.
4. reading_demands — the reading passage asks what a learner at that level can do.
5. writing_demands — the writing exercises ask what a learner at that level can do.
6. relevance — the material is grounded in the learner's documented history and \
matches the requested purpose and level.

EXPECTED LENGTH BY LEVEL (the passage should be roughly this long):
A1 60-100 words, A2 90-140, B1 140-200, B2 180-240, C1 200-280, C2 200-280.

RULES:
- Judge only the material in front of you. You never rewrite it, never repair it \
and never continue it: the teacher who wrote it does the correcting.
- Approve only when all six criteria pass. If any single criterion fails, the \
verdict is "rejected".
- Give a short, specific rationale naming the failing criteria.
- If the material is not English-learning material at all (for example code, \
arithmetic, programming instructions or any other kind of problem-solving), \
reject it: the criterion "relevance" fails.
- Answer with a single JSON object and nothing else. No markdown, no code fence, \
no commentary before or after it. The JSON object must have exactly this shape, \
with one entry for each of the six criteria:

SCHEMA
"""


class OllamaContentEvaluator(ContentEvaluator):
    """Content Evaluation Model backed by a second, different Ollama model."""

    def __init__(
        self,
        client: OllamaClient,
        *,
        model: str,
        max_tokens: int = 6000,
        keep_alive: str = "10m",
        temperature: float = 0.0,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._keep_alive = keep_alive
        self._temperature = temperature
        self.model_id = model

    async def evaluate(
        self,
        generated: "GeneratedContent",
        cefr_level: str,
        purpose: str,
    ) -> EvaluationResult:
        request = OllamaChatRequest(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": f"{EVALUATION_SYSTEM_PROMPT}{EVALUATION_SCHEMA_PROMPT}",
                },
                {"role": "user", "content": _user_message(generated, cefr_level, purpose)},
            ],
            num_predict=self._max_tokens,
            keep_alive=self._keep_alive,
            temperature=self._temperature,
        )
        response = await self._client.chat(request)
        answer = self._parse_answer(response.content)
        assessments, verdict, rationale = self._decide(answer, cefr_level)
        report_info(
            "content.evaluated",
            "provider evaluation completed",
            model_id=self.model_id,
            verdict=verdict.value,
        )
        return EvaluationResult(
            model_id=self.model_id,
            verdict=verdict,
            criterion_assessments=assessments,
            rationale=rationale,
        )

    def _parse_answer(self, content: str) -> EvaluationAnswerSchema:
        raw = extract_json_object(content)
        try:
            return EvaluationAnswerSchema.model_validate_json(raw)
        except Exception as exc:
            # A malformed answer is a retryable provider failure; the loop
            # may try again within the bound.
            raise TransientAIError(
                f"the evaluation answer does not match the expected schema: {exc}",
                provider="ollama",
            ) from exc

    def _decide(
        self, answer: EvaluationAnswerSchema, cefr_level: str
    ) -> tuple[list[CriterionAssessment], Verdict, str]:
        """Fail-closed verdict: approved only with all six criteria passing."""
        by_criterion = {item.criterion: item for item in answer.criteria}
        missing = [name for name in CRITERIA if name not in by_criterion]
        assessments: list[CriterionAssessment] = []
        for name in CRITERIA:
            item = by_criterion.get(name)
            assessments.append(
                CriterionAssessment(
                    criterion=name,
                    passed=bool(item and item.passed),
                    comment=item.comment if item else "not assessed by the evaluation model",
                )
            )
        model_approved = answer.verdict.strip().lower() == "approved"
        all_passed = all(item.passed for item in assessments)
        if model_approved and all_passed and not missing:
            return (
                assessments,
                Verdict.APPROVED,
                answer.rationale.strip() or f"All criteria passed at {cefr_level}.",
            )
        # Fail closed: anything short of a complete, all-green assessment
        # is a rejection, and the reason says why.
        reasons: list[str] = []
        if not model_approved:
            reasons.append("the evaluation model did not approve the material")
        if missing:
            reasons.append("missing criteria: " + ", ".join(missing))
        failed = [item.criterion for item in assessments if not item.passed]
        if failed:
            reasons.append("failed criteria: " + ", ".join(failed))
        rationale = answer.rationale.strip()
        detail = "; ".join(reasons)
        return (
            assessments,
            Verdict.REJECTED,
            f"{rationale} ({detail})" if rationale else detail,
        )


def _user_message(
    generated: "GeneratedContent", cefr_level: str, purpose: str
) -> str:
    """The material under assessment, plus the level and purpose it must meet."""
    import json

    material = json.dumps(generated.payload, ensure_ascii=False, indent=2)
    return (
        f"Target CEFR level: {cefr_level}\n"
        f"Requested purpose: {purpose}\n\n"
        "Material to assess:\n"
        f"{material}\n\n"
        "Assess the six criteria and answer with the JSON object now."
    )
