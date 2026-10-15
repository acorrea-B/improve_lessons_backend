"""US-10 API tests (T092): the three-dimension report with disclaimers
and no field interpretable as a proficiency score."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import headers_for, register

PROFICIENCY_SUSPECTS = (
    "proficiency_score",
    "skill_score",
    "reading_level_score",
    "cefr_estimate",
    "level_score",
)


class TestUS10Progress(unittest.TestCase):
    def test_three_sections_with_disclaimers(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/progress", headers=headers_for(token)
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            for section in ("reading", "writing", "consistency"):
                self.assertIn(section, body)
            self.assertIn("disclaimer", body)
            self.assertIn("not a formal", body["disclaimer"])
            self.assertIn("not formal proficiency", body["reading"]["disclaimer"])

    def test_insufficient_evidence_is_communicated(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/progress", headers=headers_for(token)
            )
            body = response.json()
            reading_summary = body["reading"]["summary"]
            self.assertIn("not yet enough evidence", reading_summary.lower())

    def test_no_field_is_a_proficiency_score(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/progress", headers=headers_for(token)
            )
            text = response.text
            for suspect in PROFICIENCY_SUSPECTS:
                self.assertNotIn(suspect, text)

    def test_streaks_endpoint_shape(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC")
            response = client.get(
                "/api/v1/users/me/progress/streaks", headers=headers_for(token)
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertIn("current_on_time_streak", body)
            self.assertIn("longest_on_time_streak", body)


if __name__ == "__main__":
    unittest.main()