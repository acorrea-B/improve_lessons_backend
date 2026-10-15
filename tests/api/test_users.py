"""US-1 API tests (T031): registration, validation, profile update with
profile-history append, and the authenticated read of the profile."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client


class TestUS1Registration(unittest.TestCase):
    def test_register_with_all_required_fields(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Alex Test",
                    "email": "t031@example.com",
                    "cefr_level": "A2",
                    "time_zone": "America/Bogota",
                },
            )
            self.assertEqual(response.status_code, 201, response.text)
            body = response.json()
            self.assertIn("token", body)
            self.assertEqual(body["user"]["cefr_level"], "A2")
            self.assertEqual(body["user"]["time_zone"], "America/Bogota")
            self.assertEqual(body["user"]["email"], "t031@example.com")

    def test_reject_missing_email_and_invalid_email(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.post(
                "/api/v1/auth/register", json={"name": "x", "cefr_level": "A1", "time_zone": "UTC"}
            )
            self.assertEqual(response.status_code, 422)
            response = client.post(
                "/api/v1/auth/register",
                json={"name": "x", "email": "not-an-email", "cefr_level": "A1", "time_zone": "UTC"},
            )
            self.assertEqual(response.status_code, 422)

    def test_reject_invalid_cefr(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.post(
                "/api/v1/auth/register",
                json={"name": "x", "email": "t031c@example.com", "cefr_level": "Z9", "time_zone": "UTC"},
            )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "invalid_cefr_level")

    def test_reject_invalid_time_zone(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.post(
                "/api/v1/auth/register",
                json={"name": "x", "email": "t031d@example.com", "cefr_level": "A1", "time_zone": "Mars/Olympus"},
            )
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "invalid_time_zone")

    def test_profile_update_appends_to_history(self):
        with fastapi_client() as (client, app, container, _db):
            registered = client.post(
                "/api/v1/auth/register",
                json={"name": "Alex", "email": "t031e@example.com", "cefr_level": "B1", "time_zone": "UTC"},
            )
            token = registered.json()["token"]
            user_id = registered.json()["user"]["id"]
            headers = {"authorization": f"Bearer {token}"}
            updated = client.patch("/api/v1/users/me", headers=headers, json={"cefr_level": "B2"})
            self.assertEqual(updated.status_code, 200, updated.text)
            self.assertEqual(updated.json()["cefr_level"], "B2")
            # the previous value is in profile_history
            from tests.commons.fixtures import await_on_client_loop

            history = await_on_client_loop(
                client,
                lambda: container.profile_history.list_for_user(user_id),
            )
            self.assertEqual(len(history), 1)
            self.assertIn("cefr_level", history[0].changed_fields)
            self.assertEqual(
                history[0].changed_fields["cefr_level"]["previous"], "B1"
            )

    def test_get_users_me_returns_authenticated_profile(self):
        with fastapi_client() as (client, app, container, _db):
            registered = client.post(
                "/api/v1/auth/register",
                json={"name": "Alex", "email": "t031f@example.com", "cefr_level": "B1", "time_zone": "UTC"},
            )
            token = registered.json()["token"]
            me = client.get("/api/v1/users/me", headers={"authorization": f"Bearer {token}"})
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["email"], "t031f@example.com")

    def test_unauthenticated_access_is_rejected(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.get("/api/v1/users/me")
            self.assertEqual(response.status_code, 401)



if __name__ == "__main__":
    unittest.main()