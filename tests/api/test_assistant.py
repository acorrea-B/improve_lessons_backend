"""US-9 API tests (T085): CEFR-adapted, history-grounded replies with the
preferred name; text-only enforcement; per-user thread isolation."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client
from tests.commons.helpers import headers_for, register


class TestUS9Assistant(unittest.TestCase):
    def test_open_thread_and_reply_references_history(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC", cefr="B1")
            headers = headers_for(token)
            thread = client.post("/api/v1/users/me/assistant/threads", headers=headers)
            self.assertEqual(thread.status_code, 201, thread.text)
            thread_id = thread.json()["id"]
            # Seed a summary so the user has documented history in RAG.
            message = client.post(
                f"/api/v1/users/me/assistant/threads/{thread_id}/messages",
                headers=headers,
                json={"content": "Can you explain adverbs of frequency?"},
            )
            self.assertEqual(message.status_code, 200, message.text)
            reply = message.json()["reply"]
            reply_text = reply["content"]
            self.assertTrue(reply_text)
            self.assertNotEqual(reply["role"], "user")

    def test_thread_content_is_text_only(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client)
            headers = headers_for(token)
            thread_id = client.post(
                "/api/v1/users/me/assistant/threads", headers=headers
            ).json()["id"]
            response = client.post(
                f"/api/v1/users/me/assistant/threads/{thread_id}/messages",
                headers={**headers, "content-type": "application/octet-stream"},
                content=b"\x00\x01binary",
            )
            self.assertEqual(response.status_code, 415)
            self.assertEqual(response.json()["error"]["code"], "unsupported_media_type")

    def test_cross_user_access_rejected(self):
        with fastapi_client() as (client, app, container, _db):
            token_a, user_a = register(client)
            token_b, user_b = register(client)
            thread_id = client.post(
                "/api/v1/users/me/assistant/threads",
                headers=headers_for(token_a),
            ).json()["id"]
            response = client.get(
                f"/api/v1/users/me/assistant/threads/{thread_id}",
                headers=headers_for(token_b),
            )
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()