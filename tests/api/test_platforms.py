"""US-2 API tests (T038): platforms and schedules with modality rules."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import register


class TestUS2Platforms(unittest.TestCase):
    def test_register_and_list_platform(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            response = client.post(
                "/api/v1/users/me/platforms",
                headers={"authorization": f"Bearer {token}"},
                json={"name": "Preply", "url": "https://preply.com"},
            )
            self.assertEqual(response.status_code, 201, response.text)
            listing = client.get(
                "/api/v1/users/me/platforms",
                headers={"authorization": f"Bearer {token}"},
            )
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(len(listing.json()["platforms"]), 1)

    def test_reject_invalid_url(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            response = client.post(
                "/api/v1/users/me/platforms",
                headers={"authorization": f"Bearer {token}"},
                json={"name": "x", "url": ""},
            )
            self.assertEqual(response.status_code, 422)

    def test_delete_platform_in_use_conflicts(self):
        with fastapi_client() as (client, app, container, _db):
            token, _user = register(client)
            headers = {"authorization": f"Bearer {token}"}
            platform = client.post(
                "/api/v1/users/me/platforms", headers=headers,
                json={"name": "Preply", "url": "https://preply.com"},
            ).json()
            from tests.commons.helpers import create_schedule

            schedule = create_schedule(client, token, modality="virtual", platform_id=platform["id"])
            response = client.delete(
                f"/api/v1/users/me/platforms/{platform['id']}", headers=headers
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "platform_in_use")


if __name__ == "__main__":
    unittest.main()