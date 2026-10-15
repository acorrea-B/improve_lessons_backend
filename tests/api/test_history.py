"""US-8 API tests (T080): day / week / month history retrieval, late
submissions visible with their status, "no records" messages."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (  # noqa: E402
    create_summary,
    headers_for,
    late_session_for,
    on_time_session_for,
    register,
)


def seed_history(client, container, token, *, time_zone="UTC"):
    """Seed one on-time summary; return (session, summary_response)."""
    session = on_time_session_for(client, container, token)
    return session, create_summary(client, token, session["id"])


class TestUS8History(unittest.TestCase):
    def test_day_history_returns_summaries_and_materials(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session, summary = seed_history(client, container, token)
            today = session["scheduled_end_at"][:10]
            response = client.get(
                f"/api/v1/users/me/history/days/{today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(len(body["summaries"]), 1)
            self.assertIn("materials", body)
            self.assertIn("sessions", body)

    def test_empty_day_has_clear_message(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/history/days/2026-01-01",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("message", response.json())

    def test_range_history_includes_late_status(self):
        with fastapi_client() as (client, app, container, _db):
            import datetime as dt

            token, user_id = register(client, time_zone="UTC")
            late_session = late_session_for(
                client, container, token, minutes_since_end=260
            )
            late_summary = create_summary(client, token, late_session["id"])
            self.assertEqual(late_summary.json()["submission_status"], "late")
            import datetime as dt

            today = dt.datetime.now(dt.UTC).date().isoformat()
            response = client.get(
                f"/api/v1/users/me/history?from={today}&to={today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            summaries = response.json()["summaries"]
            self.assertEqual(summaries[-1]["submission_status"], "late")

    def test_week_requires_monday(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/history/weeks/2026-10-14",  # Wednesday
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "invalid_week_boundary")
            monday = "2026-10-12"
            ok = client.get(
                f"/api/v1/users/me/history/weeks/{monday}",
                headers=headers_for(token),
            )
            self.assertEqual(ok.status_code, 200, ok.text)


if __name__ == "__main__":
    unittest.main()