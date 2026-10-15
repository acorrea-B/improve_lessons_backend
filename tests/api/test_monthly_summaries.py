"""US-7 API tests (T074): monthly rollups (calendar month in the user's
tz) and the approval-gated monthly material."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (
    closest_session, create_schedule, create_summary, headers_for, list_sessions, register,
)


class TestUS7MonthlySummary(unittest.TestCase):
    def test_monthly_counts_and_boundaries(self):
        import datetime as dt

        from tests.commons.helpers import create_schedule

        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            now = dt.datetime.now(dt.UTC)
            today = now.date().isoformat()
            from tests.commons.helpers import on_time_session_for
            session = on_time_session_for(client, container, token)
            create_summary(client, token, session["id"])
            response = client.get(
                f"/api/v1/users/me/monthly-summaries?from={today}&to={today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            monthly = response.json()["monthly_summaries"]
            self.assertTrue(monthly)
            month = monthly[0]
            self.assertEqual(month["on_time_count"], 1)
            self.assertEqual((month["month_start_at"][8:10]), "01")

    def test_empty_month_returns_summary(self):
        import datetime as dt

        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            today = dt.datetime.now(dt.UTC).date().isoformat()
            response = client.get(
                f"/api/v1/users/me/monthly-summaries?from={today}&to={today}",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["monthly_summaries"])


if __name__ == "__main__":
    unittest.main()