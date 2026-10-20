"""Bounded corrective loop (T058, US-12, constitution principle II).

Orchestrated as a LangGraph state machine (research.md § 4):

    generate → evaluate → approve / revise-or-exhaust

- The loop bound is configurable per environment (A-10, default 3); a
  bound-exhausted run FAILS and never surfaces unapproved material.
- Transient AI provider failures are absorbed inside the same bound.
- Every attempt and evaluation is returned so the ``attempt_number``
  audit trail is end-to-end reconstructible (FR-086).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from langgraph.constants import END, START
from langgraph.graph.state import StateGraph

from app.core.ports.ai_errors import NonTransientAIError, TransientAIError
from app.utils.logging import get_logger, report_error, report_info

if TYPE_CHECKING:
    from app.core.entities.materials import GenerationInputs
    from app.core.ports.content_evaluator import ContentEvaluator, EvaluationResult
    from app.core.ports.content_generator import ContentGenerator, GeneratedContent

logger = get_logger("services.content.corrective_loop")

#: The audit event of each non-approved outcome.
FAILURE_EVENTS = {
    "bound_exhausted": "content.bound_exhausted",
    "provider_failed": "content.provider_failed",
    "rejected": "content.rejected",
}


def failure_event(status: str) -> str:
    """The audit event type that matches a non-approved loop outcome."""
    return FAILURE_EVENTS.get(status, "content.rejected")


class LoopState(TypedDict):
    instruction: str
    generation_inputs: dict
    bound: int
    attempt: int
    generation: object  # GeneratedContent
    evaluation: object  # EvaluationResult
    status: str  # approved | rejected | bound_exhausted
    attempts: list
    evaluations: list


@dataclass
class LoopOutcome:
    status: str  # "approved" | "bound_exhausted" | "rejected"
    generation: "GeneratedContent | None" = None
    evaluation: "EvaluationResult | None" = None
    attempt_number: int = 0
    attempts: "list[GeneratedContent]" = field(default_factory=list)
    evaluations: "list[EvaluationResult]" = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.status == "approved"


class CorrectiveLoop:
    """The bounded generate→evaluate→revise workflow."""

    def __init__(
        self,
        generator: "ContentGenerator",
        evaluator: "ContentEvaluator",
        *,
        bound: int = 3,
    ) -> None:
        self._generator = generator
        self._evaluator = evaluator
        self._bound = max(1, bound)

    def build_graph(self):
        graph = StateGraph(LoopState)
        graph.add_node("generate", self._generate_node)
        graph.add_node("evaluate", self._evaluate_node)
        graph.add_edge(START, "generate")
        graph.add_conditional_edges(
            "generate",
            self._route_generation,
            {
                "skip_to_end": END,
                "retry": "generate",
                "evaluate": "evaluate",
            },
        )
        graph.add_conditional_edges(
            "evaluate",
            self._route,
            {
                "approved": END,
                "revise": "generate",
                "bound_exhausted": END,
            },
        )
        return graph.compile()

    async def run(self, instruction: str, inputs: "GenerationInputs") -> LoopOutcome:
        app = self.build_graph()
        state: LoopState = {
            "instruction": instruction,
            "generation_inputs": inputs.model_dump(),
            "bound": self._bound,
            "attempt": 0,
            "generation": None,
            "evaluation": None,
            "status": "rejected",
            "attempts": [],
            "evaluations": [],
        }
        final: LoopState = await app.ainvoke(state)
        if final["status"] == "rejected" and final["attempt"] >= final["bound"]:
            final["status"] = "bound_exhausted"
        outcome = LoopOutcome(
            status=final["status"],
            generation=final.get("generation"),
            evaluation=final.get("evaluation"),
            attempt_number=final["attempt"],
            attempts=list(final.get("attempts", [])),
            evaluations=list(final.get("evaluations", [])),
        )
        if not outcome.approved:
            report_error(
                failure_event(outcome.status),
                "corrective loop ended without approval",
                attempt_number=outcome.attempt_number,
                status=outcome.status,
            )
        return outcome

    # -- LangGraph nodes ------------------------------------------------------

    async def _generate_node(self, state: LoopState) -> dict:
        from app.core.entities.materials import GenerationInputs

        inputs = GenerationInputs(**state["generation_inputs"])
        attempt = state["attempt"] + 1
        instruction = state["instruction"]
        if attempt > 1 and state.get("evaluation") is not None:
            # Corrective revision: the evaluator's rationale is appended as
            # input (non-shared prompts are preserved — constitution II).
            # The revision number counts EVALUATIONS, not attempts: a
            # transient failure consumes an attempt of the bound but
            # produces no evaluation, so the rationale appended here is
            # always the one of the previous evaluation.
            revision = len(state.get("evaluations") or []) + 1
            instruction = (
                f"{instruction}\nCorrective revision {revision}: "
                f"{state['evaluation'].rationale}"
            )
        try:
            generated = await self._generator.generate(instruction, inputs)
        except NonTransientAIError as exc:
            # A permanent provider failure (unknown model, invalid
            # request, unauthorized) is not worth retrying: the loop ends
            # at once and the service reports it as unavailable.
            logger.error(
                "permanent provider failure | attempt=%d error=%s",
                attempt,
                str(exc)[:200],
            )
            return {
                "attempt": attempt,
                "generation": None,
                "attempts": [*state["attempts"]],
                "status": "provider_failed",
            }
        except TransientAIError as exc:
            # A transient failure consumes ONE attempt of the same bound
            # (A-17: no separate transient-failure counter is maintained),
            # so the provider is called at most `bound` times in total.
            if attempt >= self._bound:
                logger.error(
                    "transient provider failure beyond bound | attempt=%d bound=%d",
                    attempt,
                    self._bound,
                )
                return {
                    "attempt": attempt,
                    "attempts": [*state["attempts"]],
                    "status": "bound_exhausted",
                }
            report_info(
                "content.transient_failure",
                "absorbing transient provider failure",
                attempt=attempt,
                bound=self._bound,
                error=str(exc)[:200],
            )
            # Retry the generation: the attempt counter already accounts
            # for the consumed budget, so the next node re-enters with an
            # incremented attempt. The generation is cleared so the router
            # retries instead of re-evaluating a previous attempt.
            return {
                "attempt": attempt,
                "generation": None,
                "attempts": [*state["attempts"]],
                "status": "rejected",
            }
        attempts = [*state["attempts"], generated]
        return {
            "attempt": attempt,
            "generation": generated,
            "attempts": attempts,
        }

    async def _evaluate_node(self, state: LoopState) -> dict:
        inputs = state["generation_inputs"]
        generated = state["generation"]
        result = await self._evaluator.evaluate(
            generated, inputs["cefr_level"], inputs["purpose"]
        )
        status = "approved" if result.verdict.value == "approved" else "rejected"
        return {
            "evaluation": result,
            "status": status,
            "evaluations": [*state["evaluations"], result],
        }

    def _route(self, state: LoopState) -> str:
        if state["status"] == "approved":
            return "approved"
        if state["attempt"] >= state["bound"]:
            return "bound_exhausted"
        return "revise"

    def _route_generation(self, state: LoopState) -> str:
        """Where to go after the generation node.

        A transient failure leaves the state without a generation: the loop
        retries the generation (the attempt counter already consumed one
        unit of the bound). A permanent provider failure ends the loop.
        """
        if state["status"] in ("bound_exhausted", "provider_failed"):
            return "skip_to_end"
        if state.get("generation") is None:
            return "retry"
        return "evaluate"
