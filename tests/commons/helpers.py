"""Small test helpers shared by the API test modules."""

from __future__ import annotations

import uuid as uuid_module

from tests.commons.fixtures import await_on_client_loop


def register(client, *, cefr: str = "B1", time_zone: str = "America/Bogota") -> tuple[str, str]:
    """Register a user; returns (token, user_id)."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test Learner",
            "email": f"t-{uuid_module.uuid4().hex[:10]}@example.com",
            "cefr_level": cefr,
            "time_zone": time_zone,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["token"], body["user"]["id"]


def headers_for(token: str) -> dict:
    return {"authorization": f"Bearer {token}"}


def create_platform(client, token: str) -> dict:
    response = client.post(
        "/api/v1/users/me/platforms",
        headers=headers_for(token),
        json={"name": "Preply", "url": "https://preply.com"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_schedule(
    client,
    token: str,
    *,
    modality: str = "in_person",
    platform_id: str | None = None,
    start_time: str = "07:00",
    end_time: str = "08:00",
    recurrence: str = "daily",
) -> dict:
    payload = {
        "start_time": start_time,
        "end_time": end_time,
        "recurrence": recurrence,
        "modality": modality,
    }
    if modality == "virtual":
        payload["platform_id"] = platform_id
    else:
        payload["location"] = "Bogotá central library"
    response = client.post(
        "/api/v1/users/me/schedules",
        headers=headers_for(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_summary(client, token: str, session_id: str, content: str = "I practiced the present simple."):
    return client.post(
        f"/api/v1/users/me/sessions/{session_id}/summary",
        headers=headers_for(token),
        json={"content": content},
    )


def list_sessions(client, token: str, from_date: str, to_date: str) -> dict:
    response = client.get(
        f"/api/v1/users/me/sessions?from={from_date}&to={to_date}",
        headers=headers_for(token),
    )
    assert response.status_code == 200, response.text
    return response.json()

def closest_session(sessions: "list[dict]", target_end_utc) -> dict:
    """The session whose scheduled end is closest to the target instant."""
    from datetime import UTC, datetime

    from app.core.time.utc import require_aware_utc

    target = require_aware_utc(target_end_utc)

    def end_instant(session: dict) -> datetime:
        return datetime.fromisoformat(
            session["scheduled_end_at"].replace("Z", "+00:00")
        )

    return min(sessions, key=lambda session: abs((end_instant(session) - target).total_seconds()))


def seed_session_direct(
    client,
    container,
    user_id: str,
    *,
    minutes_since_end: int = 15,
    duration_minutes: int = 45,
    modality: str = "in_person",
    platform_url: str | None = None,
    location: str = "Room 2",
    tz: str = "UTC",
    schedule_id: str = "schedule-seeded",
) -> dict:
    """Deterministic session fixture (bypasses wall-clock schedule
    expansion): seeds a session whose end is `minutes_since_end` minutes
    from now. Positive = ended in the past; negative = starts in the
    future. Returns the serialized session document."""
    import datetime as dt

    from app.core.entities.enums import Modality
    from app.core.entities.session import Session
    from app.core.time.utc import now_utc

    now = now_utc()
    end_local = now - dt.timedelta(minutes=minutes_since_end)
    start_local = end_local - dt.timedelta(minutes=duration_minutes)

    async def _insert():
        session = Session(
            owner_user_id=user_id,
            schedule_id=schedule_id,
            scheduled_start_at=start_local,
            scheduled_end_at=end_local,
            modality=Modality(modality),
            platform_url=platform_url,
            location=None if modality == "virtual" else location,
        )
        await container.sessions_repo.insert_many([session])
        return session

    session = await_on_client_loop(client, _insert)
    return {
        "id": str(session.id),
        "schedule_id": schedule_id,
        "owner_user_id": user_id,
        "scheduled_start_at": start_local.isoformat().replace("+00:00", "Z"),
        "scheduled_end_at": end_local.isoformat().replace("+00:00", "Z"),
        "modality": modality,
        "platform_url": platform_url,
        "location": location if modality != "virtual" else None,
    }


def on_time_chain(
    client,
    container,
    *,
    cefr: str = "B1",
    time_zone: str = "UTC",
    platform: bool = False,
) -> tuple[str, str, dict]:
    """Register a user, seed a ready-to-summarize on-time session, and
    return (token, user_id, session)."""
    from tests.commons.fixtures import await_on_client_loop

    token, user_id = register(client, time_zone=time_zone, cefr=cefr)
    platform_url = None
    if platform:
        platform_url = create_platform(client, token)["url"]
    session = seed_session_direct(
        client, container, user_id, minutes_since_end=15, platform_url=platform_url
    )
    return token, user_id, session


def on_time_session_for(client, container, token: str) -> dict:
    """Deterministic on-time-window session for an existing token."""
    from tests.commons.fixtures import await_on_client_loop

    async def _identity():
        return (await container.authenticator.authenticate(token)).user_id

    user_id = await_on_client_loop(client, _identity)
    return seed_session_direct(client, container, user_id, minutes_since_end=15)


def late_session_for(
    client, container, token: str, *, minutes_since_end: int = 120
) -> dict:
    from tests.commons.fixtures import await_on_client_loop

    async def _identity():
        return (await container.authenticator.authenticate(token)).user_id

    user_id = await_on_client_loop(client, _identity)
    return seed_session_direct(
        client, container, user_id, minutes_since_end=minutes_since_end
    )


def future_session_for(client, container, token: str, *, minutes_ahead: int = 150) -> dict:
    from tests.commons.fixtures import await_on_client_loop

    async def _identity():
        return (await container.authenticator.authenticate(token)).user_id

    user_id = await_on_client_loop(client, _identity)
    return seed_session_direct(
        client, container, user_id, minutes_since_end=-minutes_ahead
    )
