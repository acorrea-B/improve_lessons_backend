"""Test fixtures (T029).

- ``mongo_isolated_database``: a unique database per test run, dropped on
  teardown (integration isolation).
- ``fastapi_client``: TestClient factory wiring the app against the
  isolated database.
- ``dummy_user_factory``: registers a user (+ token), a platform, a
  schedule and an on-time submission for re-use across tests.
"""

from __future__ import annotations

import os
import socket
import uuid as uuid_module
from contextlib import contextmanager

MongoUri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def unique_database_name() -> str:
    return f"test_{uuid_module.uuid4().hex[:12]}"


def mongo_available(port: int = 27017, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=timeout):
            return True
    except OSError:
        return False


def localstack_available(port: int = 4566, timeout: float = 0.5) -> bool:
    return mongo_available(port, timeout)


@contextmanager
def mongo_isolated_database(uri: str = MongoUri):
    """Yield a unique database name; drop it on exit."""
    from pymongo import MongoClient

    name = unique_database_name()
    client = MongoClient(uri)
    try:
        yield name
    finally:
        client.drop_database(name)
        client.close()


def build_test_app(database_name: str):
    """TestClient factory: the app wired against the isolated database."""
    import sys as _sys
    from pathlib import Path as _Path

    sys_root = _Path(__file__).resolve().parents[2]
    if str(sys_root) not in _sys.path:
        _sys.path.insert(0, str(sys_root))
    from fastapi.testclient import TestClient

    from app.core.config import Settings
    from main import create_app

    settings = Settings(
        app_env="test",
        mongodb_uri=MongoUri,
        mongodb_database=database_name,
        secrets_provider="in_memory",
        secrets_endpoint_url="http://localhost:4566",
        corrective_loop_bound=2,
    )
    app = create_app(settings)
    client = TestClient(app)  # the lifespan runs on __enter__
    return app, client


@contextmanager
def fastapi_client():
    """Yield (client, app, container, database_name) with lifespan handled."""
    database_name = unique_database_name()
    app, client = build_test_app(database_name)
    with client:
        yield client, app, app.state.container, database_name


class DummyUserFactory:
    """Registers a user / platform / schedule / session / summary chain."""

    def __init__(self, client, container, tz: str = "America/Bogota") -> None:
        self._client = client
        self._container = container
        self._tz = tz

    def register_user(self, email: str | None = None, cefr: str = "B1") -> tuple[str, str]:
        email = email or f"user-{uuid_module.uuid4().hex[:8]}@example.com"
        response = self._client.post(
            "/api/v1/auth/register",
            json={
                "name": "Dummy Learner",
                "email": email,
                "cefr_level": cefr,
                "time_zone": self._tz,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return body["token"], body["user"]["id"]

    def create_platform(self, token: str) -> dict:
        response = self._client.post(
            "/api/v1/users/me/platforms",
            headers={"authorization": f"Bearer {token}"},
            json={"name": "Preply", "url": "https://preply.com"},
        )
        assert response.status_code == 201, response.text
        return response.json()

    def create_schedule(self, token: str, platform_id: str | None = None) -> dict:
        payload = {
            "start_time": "07:00",
            "end_time": "08:00",
            "recurrence": "daily",
            "modality": "virtual" if platform_id else "in_person",
        }
        if platform_id:
            payload["platform_id"] = platform_id
        else:
            payload["location"] = "Bogotá central library"
        response = self._client.post(
            "/api/v1/users/me/schedules",
            headers={"authorization": f"Bearer {token}"},
            json=payload,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def session_ready_for_on_time_summary(self, token: str, platform_id: str | None = None) -> dict:
        """Create a schedule whose session ended ~15 minutes ago, so a
        summary submitted now is on_time (within the 30-minute window)."""
        return self._session_at_window(token, minutes_since_end=15, platform_id=platform_id)

    def session_late_window(self, token: str, platform_id: str | None = None) -> dict:
        """A session ended 2 hours ago: a summary submitted now is late."""
        return self._session_at_window(token, minutes_since_end=120, platform_id=platform_id)

    def session_future(self, token: str, platform_id: str | None = None) -> dict:
        """A session starting more than half a day in the future: a summary
        submitted now carries the pre-start flag."""
        return self._session_at_window(token, minutes_since_end=-360, platform_id=platform_id)

    def _session_at_window(self, token: str, *, minutes_since_end: int, platform_id: str | None) -> dict:
        from datetime import timedelta

        from app.core.time.utc import now_utc

        now = now_utc()
        end_local = now + timedelta(minutes=-minutes_since_end)
        start_local = end_local - timedelta(minutes=45)
        def hhmm(moment) -> str:
            local = moment
            return f"{local.hour:02d}:{local.minute:02d}"
        payload = {
            "start_time": hhmm(start_local),
            "end_time": hhmm(end_local),
            "recurrence": "daily",
            "modality": "virtual" if platform_id else "in_person",
        }
        if platform_id:
            payload["platform_id"] = platform_id
        else:
            payload["location"] = "Bogotá central library"
        response = self._client.post(
            "/api/v1/users/me/schedules",
            headers={"authorization": f"Bearer {token}"},
            json=payload,
        )
        assert response.status_code == 201, response.text
        schedule = response.json()
        sessions = self._sessions_for(token, schedule["id"])
        target = min(sessions, key=lambda s: s["scheduled_end_at"])
        today = now.date().isoformat()
        same_day = [s for s in sessions if s["scheduled_start_at"][:10] == today]
        return (same_day or sessions)[-1]

    def _sessions_for(self, token: str, schedule_id: str) -> list[dict]:
        from datetime import date

        from app.core.time.utc import now_utc

        today = now_utc().date().isoformat()
        response = self._client.get(
            f"/api/v1/users/me/sessions?from={today}&to={today}",
            headers={"authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        sessions = response.json()["sessions"]
        mine = [s for s in sessions if s.get("schedule_id") == schedule_id]
        assert mine, "schedule expansion produced no session today"
        return mine

    def submit_summary(self, token: str, session_id: str, content: str | None = None) -> dict:
        response = self._client.post(
            f"/api/v1/users/me/sessions/{session_id}/summary",
            headers={"authorization": f"Bearer {token}"},
            json={"content": content or "I practiced the present simple."},
        )
        assert response.status_code == 201, response.text
        return response.json()

    def submit_summary_response(self, token: str, session_id: str, payload: dict | None = None):
        """Submit a summary without asserting success (returns response)."""
        return self._client.post(
            f"/api/v1/users/me/sessions/{session_id}/summary",
            headers={"authorization": f"Bearer {token}"},
            json=payload or {"content": "I practiced the present simple."},
        )

    def fetch_material_for_session(self, token: str, session_id: str):
        return self._client.get(
            f"/api/v1/users/me/sessions/{session_id}/summary/material",
            headers={"authorization": f"Bearer {token}"},
        )

def await_on_client_loop(client, async_callable):
    """Run an async callable on the TestClient's application loop."""
    import functools

    portal = getattr(client, "portal", None)
    if portal is None:
        raise RuntimeError("the TestClient must be entered (with client:) first")

    async def _run():
        return await async_callable()

    return portal.call(_run)
