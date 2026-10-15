"""US-4 API tests (T049): on-time/late derivation, pre-start flag,
duplicate rejection, empty-content rejection — in several time zones."""

from __future__ import annotations

import unittest
from zoneinfo import ZoneInfo

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (  # noqa: E402
    create_platform,
    create_platform,
    create_summary,
    headers_for,
    list_sessions,
    register,
)

NOW = "now"


def make_session(
    client,
    token,
    *,
    minutes_since_end: int,
    platform_id: str | None = None,
    time_zone: str = "UTC",
    container=None,
):
    """Deterministic fixture: a session ending `minutes_since_end` minutes
    from now (positive = ended in the past; the submission that follows is
    on_time inside the 30-minute window or late outside it)."""
    from tests.commons.fixtures import await_on_client_loop
    from tests.commons.helpers import seed_session_direct

    assert container is not None

    async def _identity():
        context = await container.authenticator.authenticate(token)
        return context.user_id

    user_id = await_on_client_loop(client, _identity)
    return seed_session_direct(
        client,
        container,
        user_id,
        minutes_since_end=minutes_since_end,
        tz=time_zone,
        platform_url="https://preply.com" if platform_id else None,
    )


class TestUS4SubmissionStatus(unittest.TestCase):
    def test_on_time_within_30_minute_window(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC")
            session = make_session(client, token, minutes_since_end=15, container=container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201, summary.text)
            self.assertEqual(summary.json()["submission_status"], "on_time")
            self.assertFalse(summary.json()["submitted_before_session_start"])

    def test_late_outside_window(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="America/Bogota")
            session = make_session(client, token, minutes_since_end=120, time_zone="America/Bogota", container=container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201, summary.text)
            self.assertEqual(summary.json()["submission_status"], "late")

    def test_late_in_second_time_zone(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="Asia/Kolkata")
            session = make_session(client, token, minutes_since_end=200, time_zone="Asia/Kolkata", container=container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.json()["submission_status"], "late")

    def test_duplicate_summary_rejected(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            session = make_session(client, token, minutes_since_end=15, time_zone="UTC", container=container)
            first = create_summary(client, token, session["id"])
            self.assertEqual(first.status_code, 201)
            second = create_summary(client, token, session["id"])
            self.assertEqual(second.status_code, 409)
            self.assertEqual(second.json()["error"]["code"], "summary_already_exists")

    def test_empty_content_rejected(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            session = make_session(client, token, minutes_since_end=15, time_zone="UTC", container=container)
            response = create_summary(client, token, session["id"], content="   ")
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "empty_content")

    def test_pre_start_flag_set_when_submitted_before_start(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            import datetime as dt

            from tests.commons.helpers import create_schedule

            zone = ZoneInfo("America/Bogota")
            now = dt.datetime.now(dt.UTC)
            now_local = now.astimezone(zone)
            schedule = create_schedule(
                client,
                token,
                start_time=f"{now_local + dt.timedelta(minutes=120):%H:%M}",
                end_time=f"{now_local + dt.timedelta(minutes=180):%H:%M}",
            )
            from tests.commons.helpers import closest_session, list_sessions

            today = now.date().isoformat()
            mine = [
                s
                for s in list_sessions(client, token, (now - dt.timedelta(days=1)).date().isoformat(), (now + dt.timedelta(days=1)).date().isoformat())["sessions"]
                if s.get("schedule_id") == schedule["id"]
            ]
            session = closest_session(mine, now + dt.timedelta(minutes=150))
            response = create_summary(client, token, session["id"])
            self.assertEqual(response.status_code, 201, response.text)
            self.assertTrue(response.json()["submitted_before_session_start"])

    def test_late_submission_is_never_reclassified(self):
        """Constitution IV: a late arrival keeps its record AND the first
        record keeps its own status (duplicate is rejected, not merged)."""
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="America/Bogota")
            session = make_session(client, token, minutes_since_end=15, time_zone="America/Bogota", container=container)
            first = create_summary(client, token, session["id"], content="First version of the record.")
            self.assertEqual(first.json()["submission_status"], "on_time")
            duplicate = create_summary(client, token, session["id"], content="Late second attempt.")
            self.assertEqual(duplicate.status_code, 409)
            fetched = client.get(
                f"/api/v1/users/me/summaries/{first.json()['id']}",
                headers=headers_for(token),
            )
            self.assertEqual(fetched.json()["content"], "First version of the record.")


if __name__ == "__main__":
    unittest.main()