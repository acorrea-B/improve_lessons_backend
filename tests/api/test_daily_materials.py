"""US-5 API tests (T062): the daily material is approved-gated, CEFR
tagged, and grounded in history; unapproved material never surfaces."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (
    create_schedule,
    create_summary,
    headers_for,
    list_sessions,
    register,
)


def on_time_session(client, token, container):
    from tests.commons.helpers import on_time_session_for
    return on_time_session_for(client, container, token)

    now = dt.datetime.now(dt.UTC)
    schedule = create_schedule(
        client, token,
        start_time=f"{now - dt.timedelta(minutes=60):%H:%M}",
        end_time=f"{now - dt.timedelta(minutes=15):%H:%M}",
    )
    today = now.date().isoformat()
    sessions = list_sessions(client, token, today, today)["sessions"]
    mine = [s for s in sessions if s.get("schedule_id") == schedule["id"]]
    from tests.commons.helpers import closest_session
    return closest_session(mine, now - dt.timedelta(minutes=15))


class TestUS5DailyMaterial(unittest.TestCase):
    def test_material_delivered_after_summary(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201, summary.text)
            material = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertEqual(material.status_code, 200, material.text)
            body = material.json()
            self.assertIn("reading", body)
            self.assertIn("writing_exercises", body)
            self.assertIn("generation_id", body)
            self.assertIn("evaluation_id", body)
            # history grounding: the deterministic generator references the
            # documented summary content
            self.assertIn("documented", str(body["reading"]["body"]).lower())

    def test_unapproved_material_never_returned(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            # Force-replace the loop with a rejecting evaluator bound small
            from app.adapters.external.ai.deterministic_ai import (
                DeterministicContentGenerator,
            )
            from app.core.entities.content_workflow import CriterionAssessment
            from app.core.entities.enums import Verdict
            from app.core.ports.content_evaluator import EvaluationResult
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
                        rationale="never approved",
                    )

            rejecting = CorrectiveLoop(
                DeterministicContentGenerator(), RejectingEvaluator(), bound=2
            )
            container.workflow._loop = rejecting
            material = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertIn(material.status_code, (404, 503))
            self.assertNotIn("reading", material.json())

    def test_material_listed_only_after_summary(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            empty = client.get(
                "/api/v1/users/me/daily-materials",
                headers=headers_for(token),
            )
            self.assertEqual(empty.status_code, 200)
            self.assertEqual(empty.json()["materials"], [])


if __name__ == "__main__":
    unittest.main()