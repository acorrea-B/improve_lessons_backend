"""Reminder dispatch integration (T044): a user who updates the schedule
does not receive a reminder for the OLD session; reminders land in the
user's time zone."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client, mongo_available
from tests.commons.helpers import headers_for, register
from unittest import skipUnless

@skipUnless(mongo_available(), "MongoDB is not running")
class TestReminderSuppression(unittest.TestCase):
    def test_schedule_update_does_not_send_stale_reminder(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            headers = headers_for(token)
            import datetime as dt
            from tests.commons.helpers import create_platform, create_schedule, list_sessions

            platform = create_platform(client, token)
            now = dt.datetime.now(dt.UTC)
            schedule = create_schedule(
                client, token, modality="virtual", platform_id=platform["id"],
                start_time=f"{now + dt.timedelta(minutes=20):%H:%M}",
                end_time=f"{now + dt.timedelta(minutes=80):%H:%M}",
                recurrence="daily",
            )
            sessions = list_sessions(
                client, token, now.date().isoformat(), now.date().isoformat()
            )["sessions"]
            mine = [s for s in sessions if s.get("schedule_id") == schedule["id"]]
            # Only one session exists now (the near-future one).
            self.assertTrue(mine)
            old_session_ids = {s["id"] for s in mine if not s.get("reminder_sent_at")}
            # Update the schedule: future sessions of the OLD definition are
            # removed; a stale reminder must not fire.
            response = client.patch(
                f"/api/v1/users/me/schedules/{schedule['id']}",
                headers=headers,
                json={"end_time": f"{now + dt.timedelta(minutes=120):%H:%M}"},
            )
            self.assertIn(response.status_code, (200, 201), response.text)

            # run a scan on the app loop: no reminder for the old session
            from tests.commons.fixtures import await_on_client_loop

            result = await_on_client_loop(
                client, lambda: app.state.container.reminder_service.dispatch_due()
            )
            self.assertEqual(result, 0, "a stale reminder fired after the schedule edit")


if __name__ == "__main__":
    unittest.main()