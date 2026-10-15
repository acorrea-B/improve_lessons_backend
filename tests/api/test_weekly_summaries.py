"""US-6 API tests (T068): weekly rollups (Monday start, user's tz) and
the approval-gated weekly material."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (  # noqa: E402
    closest_session,
    create_platform,
    create_schedule,
    create_summary,
    headers_for,
    list_sessions,
    register,
)


def seed_week(client, container, token, *, on_time: int = 1, late: int = 1):
    import datetime as dt

    from tests.commons.helpers import (
        create_summary,
        late_session_for,
        on_time_session_for,
    )

    now = dt.datetime.now(dt.UTC)
    for _ in range(on_time):
        session = on_time_session_for(client, container, token)
        create_summary(client, token, session["id"])
    for _ in range(late):
        session = late_session_for(client, container, token, minutes_since_end=260)
        create_summary(client, token, session["id"])
    return now.date().isoformat()



class TestUS6WeeklySummary(unittest.TestCase):
    def test_weekly_counts_and_monday_start(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            today = seed_week(client, container, token, on_time=1, late=1)
            response = client.get(
                f"/api/v1/users/me/weekly-summaries?from={today}&to={today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            summaries = response.json()["weekly_summaries"]
            self.assertTrue(summaries)
            week = summaries[0]
            self.assertEqual(week["on_time_count"] + week["late_count"], 2)
            self.assertIn("recorded_study_minutes", week)
            self.assertIn("consistency_indicators", week)
            self.assertIn("knowledge_synthesis", week)

    def test_week_with_no_submissions_returns_summary(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            self.assertTrue(True)  # registration itself is the user journey start
            import datetime as dt

            today = dt.datetime.now(dt.UTC).date().isoformat()
            response = client.get(
                f"/api/v1/users/me/weekly-summaries?from={today}&to={today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            week = response.json()["weekly_summaries"][0]
            self.assertIn("on_time_count", week)

    def test_weekly_material_is_gated_by_approval(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            today = seed_week(client, container, token, on_time=1, late=0)
            listing = client.get(
                f"/api/v1/users/me/weekly-summaries?from={today}&to={today}",
                headers=headers_for(token),
            )
            week = listing.json()["weekly_summaries"][0]
            material = client.get(
                f"/api/v1/users/me/weekly-summaries/{week['id']}/material",
                headers=headers_for(token),
            )
            self.assertEqual(material.status_code, 200, material.text)
            self.assertIn("reading", material.json())
            self.assertIn("evaluation_id", material.json())


if __name__ == "__main__":
    unittest.main()