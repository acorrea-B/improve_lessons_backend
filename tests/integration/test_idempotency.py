"""Idempotency tests (T030, contract § Conventions): a repeated write with
the same Idempotency-Key replays the original response; two concurrent
writes with the same key do not both reach the underlying service."""

from __future__ import annotations

import json
import unittest

from tests.commons.fixtures import await_on_client_loop, fastapi_client, mongo_available
from tests.commons.helpers import (  # noqa: E402
    create_platform,
    create_schedule,
    create_summary,
    headers_for,
    list_sessions,
    register,
)
from unittest import skipUnless


def on_time_session(client, token, container):
    from tests.commons.helpers import on_time_session_for
    return on_time_session_for(client, container, token)

    from tests.commons.helpers import create_schedule

    now = dt.datetime.now(dt.UTC)
    schedule = create_schedule(
        client, token,
        start_time=f"{now - dt.timedelta(minutes=60):%H:%M}",
        end_time=f"{now - dt.timedelta(minutes=15):%H:%M}",
    )
    today = now.date().isoformat()
    sessions = list_sessions(client, token, (now - dt.timedelta(days=1)).date().isoformat(), (now + dt.timedelta(days=1)).date().isoformat())["sessions"]
    mine = [s for s in sessions if s.get("schedule_id") == schedule["id"]]
    from tests.commons.helpers import closest_session

    return closest_session(mine, now - dt.timedelta(minutes=15))


@skipUnless(mongo_available(), "MongoDB is not running")
class TestIdempotency(unittest.TestCase):
    def test_repeat_write_with_same_key_replays_response(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            headers = {**headers_for(token), "idempotency-key": "submit-summary-1"}
            session = on_time_session(client, token, container)
            first = client.post(
                f"/api/v1/users/me/sessions/{session['id']}/summary",
                headers=headers,
                json={"content": "Only once."},
            )
            self.assertEqual(first.status_code, 201, first.text)
            second = client.post(
                f"/api/v1/users/me/sessions/{session['id']}/summary",
                headers={**headers_for(token), "idempotency-key": "submit-summary-1"},
                json={"content": "Only once."},
            )
            self.assertEqual(second.status_code, 201)
            self.assertEqual(second.json(), first.json())

    def test_concurrent_writes_with_same_key_do_not_double_apply(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = on_time_session(client, token, container)
            with open("/dev/null", "w"):
                pass
            import concurrent.futures

            def post(_: int):
                return client.post(
                    f"/api/v1/users/me/sessions/{session['id']}/summary",
                    headers={**headers_for(token), "idempotency-key": "concurrent-1"},
                    json={"content": "Concurrent write."},
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(post, [0, 1]))
            bodies = [response.status_code for response in responses]
            # at most ONE request reaches the service; the other replays or
            # is told to retry.
            self.assertEqual(sum(1 for code in bodies if code == 201), 1, bodies)
            summaries = client.get(
                "/api/v1/users/me/summaries", headers=headers_for(token)
            ).json()["summaries"]
            self.assertEqual(len(summaries), 1)


if __name__ == "__main__":
    unittest.main()