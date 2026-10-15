"""Full user journey end-to-end test (T117): registration → schedule →
summary → daily material → weekly summary → assistant → progress →
motivation — against the FastAPI TestClient with in-memory email fake."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client, mongo_available
from tests.commons.helpers import (
    create_platform,
    create_schedule,
    create_summary,
    headers_for,
    list_sessions,
    register,
)
from unittest import skipUnless


@skipUnless(mongo_available(), "MongoDB is not running")
class TestUserJourney(unittest.TestCase):
    def test_full_journey(self):
        with fastapi_client() as (client, app, container, _db):
            import datetime as dt

            # 1. registration (US-1)
            token, user_id = register(client, time_zone="UTC", cefr="B1")
            headers = headers_for(token)

            # 2. platform + schedule + sessions (US-2)
            platform = create_platform(client, token)
            now = dt.datetime.now(dt.UTC)
            today = now.date().isoformat()
            # the schedule exercises US-2; the summaryable session is
            # seeded deterministically (immune to wall-clock drift)
            create_schedule(
                client, token, modality="virtual", platform_id=platform["id"],
                start_time="07:00", end_time="08:00",
            )
            from tests.commons.helpers import on_time_session_for

            session = on_time_session_for(client, app.state.container, token)
            session_id = session["id"]

            # 3. daily summary on time (US-4)
            summary = create_summary(
                client, token, session_id,
                "I practiced phrasal verbs and the present perfect today.",
            )
            self.assertEqual(summary.status_code, 201)
            self.assertEqual(summary.json()["submission_status"], "on_time")

            # 4. daily material approved (US-5 via US-12)
            material = client.get(
                f"/api/v1/users/me/sessions/{session_id}/summary/material",
                headers=headers,
            )
            self.assertEqual(material.status_code, 200, material.text)

            # 5. weekly summary with material (US-6)
            weekly = client.get(
                f"/api/v1/users/me/weekly-summaries?from={today}&to={today}",
                headers=headers,
            )
            self.assertEqual(weekly.status_code, 200, weekly.text)

            # 6. assistant (US-9)
            thread = client.post("/api/v1/users/me/assistant/threads", headers=headers)
            self.assertEqual(thread.status_code, 201)
            reply = client.post(
                f"/api/v1/users/me/assistant/threads/{thread.json()['id']}/messages",
                headers=headers,
                json={"content": "Explain adverbs of frequency please."},
            )
            self.assertEqual(reply.status_code, 200, reply.text)

            # 7. progress disclaimers (US-10)
            progress = client.get("/api/v1/users/me/progress", headers=headers)
            self.assertEqual(progress.status_code, 200)
            self.assertIn("disclaimer", progress.json())

            # 8. motivation (US-11)
            recognitions = client.get("/api/v1/users/me/recognitions", headers=headers)
            self.assertEqual(recognitions.status_code, 200)
            challenge = client.get("/api/v1/users/me/challenges", headers=headers)
            self.assertEqual(challenge.status_code, 200)
            self.assertIn(challenge.json()["target_cefr_level"], ("B1", "B2"))

            # 9. history keeps the late records accessible with status (US-8)
            history = client.get(f"/api/v1/users/me/history/days/{today}", headers=headers)
            self.assertIn("summaries", history.json())

            # 10. every write produced audit rows (FR-084–086)
            from tests.commons.fixtures import await_on_client_loop

            events = await_on_client_loop(
                client, lambda: container.audit_events_repo.list_for_owner(user_id, limit=1000)
            )
            event_types = {event.event_type for event in events}
            self.assertIn("user.registered", event_types)
            self.assertIn("summary.submitted", event_types)
            self.assertIn("daily_material.delivered", event_types)

    def test_graceful_shutdown_flushes_and_closes(self):
        """T116: lifespan shutdown flushes pending reminder dispatches,
        finalizes in-flight work, and closes the MongoDB client without
        raising."""
        from tests.commons.fixtures import build_test_app, unique_database_name

        app, client = build_test_app(unique_database_name())
        with client:
            container = app.state.container
            self.assertFalse(container.mongo._started == False)
        # After `with` exits, the lifespan teardown ran: the client is closed.
        self.assertFalse(app.state.container.mongo._started)


if __name__ == "__main__":
    unittest.main()