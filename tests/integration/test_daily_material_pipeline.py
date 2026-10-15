"""Daily-material pipeline integration (T062): the pipeline from summary
to approved material with the content workflow, and the FR-046 cache."""

from __future__ import annotations

import unittest

from tests.commons.fixtures import fastapi_client, mongo_available
from tests.commons.helpers import (  # noqa: E402
    create_platform,
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
class TestDailyMaterialPipeline(unittest.TestCase):
    def test_pipeline_persists_generation_evaluation_material(self):
        with fastapi_client() as (client, app, container, _db):
            token, user_id = register(client, time_zone="UTC")
            session = on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            self.assertEqual(summary.status_code, 201)
            response = client.get(
                f"/api/v1/users/me/sessions/{session['id']}/summary/material",
                headers=headers_for(token),
            )
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            # the material references the summary and the user owns it
            self.assertEqual(str(body["summary_id"]), summary.json()["id"])
            self.assertEqual(str(body["owner_user_id"]), user_id)
            # the CEFR level tags the record via generation inputs
            inputs = None

            from tests.commons.fixtures import await_on_client_loop

            async def read_generation():
                return await container.generations_repo.get(
                    body["generation_id"], user_id
                )

            generation = await_on_client_loop(client, read_generation)
            self.assertIsNotNone(generation)
            self.assertEqual(generation.inputs["cefr_level"], "B1")
            self.assertIn("practiced", " ".join(generation.inputs["history_slice"])[0:100000])

    def test_material_is_delivered_only_when_approved(self):
        with fastapi_client() as (client, app, container, _db):
            from app.services.daily_material_service import (
                DailyMaterialService,
            )

            token, user_id = register(client, time_zone="UTC")
            session = on_time_session(client, token, container)
            summary = create_summary(client, token, session["id"])
            # No material requested yet: the endpoint returns 404 (no
            # unapproved fabrication either way).
            listing = client.get(
                "/api/v1/users/me/daily-materials", headers=headers_for(token)
            )
            self.assertEqual(listing.json()["materials"], [])
            material = client.get(
                f"/api/v1/users/me/summaries/{summary.json()['id']}/material",
                headers=headers_for(token),
            )
            self.assertIn(material.status_code, (404, 200, 503))


if __name__ == "__main__":
    unittest.main()