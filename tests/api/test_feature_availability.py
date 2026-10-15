"""US-13 API tests (T103): the global feature switch, gated endpoints with
the documented message, and changes taking effect without re-login."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import headers_for, register


class TestUS13FeatureAvailability(unittest.TestCase):
    def test_system_features_are_public(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.get("/api/v1/system/features")
            self.assertEqual(response.status_code, 200, response.text)
            features = response.json()["features"]
            self.assertIn("reminders", features)
            self.assertTrue(features["reminders"])

    def test_health_is_public(self):
        with fastapi_client() as (client, app, container, _db):
            response = client.get("/api/v1/system/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ok")

    def test_disabled_feature_gates_endpoint_and_takes_effect_without_relogin(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            headers = headers_for(token)
            # disabled via configuration (the global switch)
            from tests.commons.fixtures import await_on_client_loop

            await_on_client_loop(
                client,
                lambda: app.state.container.services.feature_availability.set_state(
                    "assistant", False, updated_by="system"
                ),
            )
            # takes effect WITHOUT re-login: the same token gets rejected
            thread = client.post("/api/v1/users/me/assistant/threads", headers=headers)
            self.assertEqual(thread.status_code, 403, thread.text)
            self.assertEqual(thread.json()["error"]["code"], "feature_not_available")

            # re-enable: same token works again
            await_on_client_loop(
                client,
                lambda: app.state.container.services.feature_availability.set_state(
                    "assistant", True, updated_by="system"
                ),
            )
            thread = client.post("/api/v1/users/me/assistant/threads", headers=headers)
            self.assertEqual(thread.status_code, 201)


if __name__ == "__main__":
    unittest.main()