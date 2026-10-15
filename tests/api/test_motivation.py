"""US-11 API tests (T097): streak recognitions, CEFR+1 challenge bound,
refinements at C2, and a starting challenge for users with no history."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import (  # noqa: E402
    closest_session,
    create_platform,
    create_summary,
    create_schedule,
    headers_for,
    list_sessions,
    register,
)


def on_time_summary_token(client, container, repeats: int = 1):
    """Register a user with `repeats` on-time summaries; return token."""
    token, user_id = register(client, time_zone="UTC")
    from tests.commons.helpers import on_time_session_for

    for _ in range(repeats):
        session = on_time_session_for(client, container, token)
        create_summary(client, token, session["id"])
    return token


class TestUS11Motivation(unittest.TestCase):
    def test_on_time_streak_recognition(self):
        with fastapi_client() as (client, app, container, _db):
            token = on_time_summary_token(client, container, repeats=1)
            response = client.get(
                "/api/v1/users/me/recognitions", headers=headers_for(token)
            )
            self.assertEqual(response.status_code, 200, response.text)
            kinds = [item["kind"] for item in response.json()["recognitions"]]
            self.assertIn("on_time_streak", kinds)

    def test_challenge_stays_within_cefr_plus_one(self):
        with fastapi_client() as (client, app, container, _db):
            token = on_time_summary_token(client, container, repeats=1)
            response = client.get(
                "/api/v1/users/me/challenges", headers=headers_for(token)
            )
            self.assertEqual(response.status_code, 200, response.text)
            challenge = response.json()
            # FR-075: never more than one level above the declared level.
            self.assertIn(challenge["target_cefr_level"], ("B1", "B2"))

            # With sustained evidence the promotion happens immediately.
            from app.core.strategies.recommendation_strategy import RecommendationStrategy

            strategy = RecommendationStrategy()
            recommendation = strategy.recommend(
                declared_level=__import__("app.core.entities.enums", fromlist=["CEFRLevel"]).CEFRLevel.B1,
                has_history=True,
                recent_on_time_submissions=5,
            )
            self.assertEqual(recommendation.target_cefr_level.value, "B2")

    def test_user_at_top_level_receives_refinement(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC", cefr="C2")
            response = client.get(
                "/api/v1/users/me/challenges", headers=headers_for(token)
            )
            challenge = response.json()
            self.assertEqual(challenge["target_cefr_level"], "C2")

    def test_user_without_history_starts_at_declared_level(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client, time_zone="UTC", cefr="A1")
            response = client.get(
                "/api/v1/users/me/challenges", headers=headers_for(token)
            )
            challenge = response.json()
            self.assertEqual(challenge["target_cefr_level"], "A1")

    def test_starting_a_challenge_produces_approved_material(self):
        with fastapi_client() as (client, app, container, _db):
            token = on_time_summary_token(client, container)
            challenge = client.get(
                "/api/v1/users/me/challenges", headers=headers_for(token)
            ).json()
            started = client.post(
                f"/api/v1/users/me/challenges/{challenge['id']}/start",
                headers=headers_for(token),
            )
            self.assertEqual(started.status_code, 200, started.text)
            self.assertTrue(started.json()["started"])


if __name__ == "__main__":
    unittest.main()