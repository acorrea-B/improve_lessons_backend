"""US-12 integration tests against real MongoDB (T056, T061): the
content workflow persists every attempt, and the FR-046 contract —
a persisted approved material is served from cache with no new loop run
or evaluation rows."""

from __future__ import annotations

import unittest
from datetime import timedelta

from tests.commons.fixtures import (
    await_on_client_loop,
    fastapi_client,
    mongo_available,
    unique_database_name,
)
from tests.commons.helpers import (  # noqa: E402
    create_platform,
    create_summary,
    headers_for,
    list_sessions,
    register,
)


def _make_on_time_session(client, token, container):
    from tests.commons.helpers import on_time_session_for
    return on_time_session_for(client, container, token)

    from tests.commons.helpers import create_schedule

    now = dt.datetime.now(dt.UTC)
    schedule = create_schedule(
        client, token,
        start_time=f"{now - dt.timedelta(minutes=60):%H:%M}",
        end_time=f"{now - dt.timedelta(minutes=15):%H:%M}",
    )
    today = now.date().isoformat()
    sessions = list_sessions(client, token, (now - dt.timedelta(days=1)).date().isoformat(), (now + dt.timedelta(days=1)).date().isoformat())["sessions"]
    mine = [s for s in sessions if s.get("schedule_id") == schedule["id"]]
    from tests.commons.helpers import closest_session

    return closest_session(mine, now - dt.timedelta(minutes=15))


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestContentWorkflowPersistence(unittest.TestCase):
    def test_generation_and_evaluation_rows_are_persisted(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = _make_on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201)
            response = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            material = response.json()

            generation_id = material["generation_id"]
            evaluation_id = material["evaluation_id"]

            async def fetch_rows():
                generation = await container.generations_repo.get(generation_id, user_id)
                evaluation = await container.evaluations_repo.get(evaluation_id, user_id)
                count = await container.evaluations_repo.count_by_generation(
                    generation_id, user_id
                )
                return generation, evaluation, count

            generation, evaluation, count = await_on_client_loop(client, fetch_rows)
            self.assertIsNotNone(generation)
            self.assertIsNotNone(evaluation)
            self.assertEqual(evaluation.verdict.value, "approved")
            self.assertEqual(evaluation.attempt_number, 1)
            self.assertEqual(count, 1)

    def test_fr046_repeated_fetch_replays_without_new_loop_run(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = _make_on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            first = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertEqual(first.status_code, 200, first.text)
            material = first.json()

            evaluations_before = await_on_client_loop(
                client,
                lambda: container.evaluations_repo.count_by_generation(
                    material["generation_id"], user_id
                ),
            )
            audits_before = await_on_client_loop(
                client,
                lambda: container.audit_events_repo.list_for_owner(
                    user_id, limit=1000
                ),
            )
            generated_before = len(
                [e for e in audits_before if e.event_type == "content.generated"]
            )

            # two concurrent fetches
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(
                        client.get,
                        f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                        headers=headers_for(token),
                    )
                    for _ in range(2)
                ]
                responses = [future.result() for future in futures]
            for response in responses:
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(
                    response.json()["evaluation_id"], material["evaluation_id"]
                )

            evaluations_after = await_on_client_loop(
                client,
                lambda: container.evaluations_repo.count_by_generation(
                    material["generation_id"], user_id
                ),
            )
            audits_after = await_on_client_loop(
                client,
                lambda: container.audit_events_repo.list_for_owner(
                    user_id, limit=1000
                ),
            )
            generated_after = len(
                [e for e in audits_after if e.event_type == "content.generated"]
            )
            self.assertEqual(evaluations_after, evaluations_before)
            self.assertEqual(generated_after, generated_before)
            # (c) no new content.evaluated/content.generated audit rows
            self.assertEqual(len(audits_after), len(audits_before))

    def test_rejected_material_is_never_exposed(self):
        """A loop that exhausts its bound surfaces an error, never material."""
        with fastapi_client() as (client, app, container, _db):
            from app.adapters.external.ai.deterministic_ai import (
                DeterministicContentEvaluator,
                DeterministicContentGenerator,
            )
            from app.core.ports.content_evaluator import EvaluationResult
            from app.core.entities.enums import Verdict
            from app.core.entities.content_workflow import CriterionAssessment
            from app.services.content.corrective_loop import CorrectiveLoop

            class RejectingEvaluator:
                model_id = "rejecting"

                async def evaluate(self, generated, cefr_level, purpose):
                    return EvaluationResult(
                        model_id=self.model_id,
                        verdict=Verdict.REJECTED,
                        criterion_assessments=[
                            CriterionAssessment(criterion="relevance", passed=False)
                        ],
                        rationale="test rejection",
                    )

            loop = CorrectiveLoop(
                DeterministicContentGenerator(), RejectingEvaluator(), bound=2
            )
            container.loop = loop
            container.workflow._loop = loop

            token, user_id = register(client, time_zone="UTC")
            session = _make_on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201)
            response = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertIn(response.status_code, (404, 503))
            body = response.json()
            self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()