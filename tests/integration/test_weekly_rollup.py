"""Weekly rollup integration (T068): counts reflect the actual mix, the
boundary is Monday 00:00 in the user's tz, and rollups are idempotent."""

from __future__ import annotations

import unittest
from asyncio import run
from datetime import timedelta

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import (
    AuditEventRepository,
    SessionRepository,
    SummaryRepository,
    UserRepository,
    WeeklyMaterialRepository,
    WeeklySummaryRepository,
)
from app.core.entities.daily_summary import DailySummary
from app.core.entities.enums import CEFRLevel, Modality, SubmissionStatus
from app.core.entities.session import Session
from app.core.entities.user import User
from app.core.time.utc import now_utc
from app.services.content.corrective_loop import CorrectiveLoop
from app.adapters.external.ai.deterministic_ai import (
    DeterministicContentEvaluator,
    DeterministicContentGenerator,
)
from app.services.content.content_workflow import ContentWorkflowService
from app.services.rollup_services import WeeklyRollupService
from app.core.strategies.week_boundary_strategy import week_start_for_wall_clock

from tests.commons.fixtures import mongo_available, mongo_isolated_database


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestWeeklyRollup(unittest.TestCase):
    def test_counts_and_week_boundary(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    users = UserRepository(mongo)
                    sessions = SessionRepository(mongo)
                    summaries = SummaryRepository(mongo)
                    weekly = WeeklySummaryRepository(mongo)
                    weekly_materials = WeeklyMaterialRepository(mongo)
                    audits = AuditEventRepository(mongo)
                    now = now_utc()
                    user = User(
                        name="Rollup", email="rollup@example.com",
                        cefr_level=CEFRLevel.B1, time_zone="Europe/Madrid",
                        created_at=now, updated_at=now,
                    )
                    await users.insert_user(user)
                    owner = str(user.id)
                    # one on-time and one late summary this week
                    for status, offset_minutes in (
                        (SubmissionStatus.ON_TIME, 15),
                        (SubmissionStatus.LATE, 600),
                    ):
                        session = Session(
                            owner_user_id=owner,
                            schedule_id=f"sch-{status.value}",
                            scheduled_start_at=now - timedelta(minutes=offset_minutes + 45),
                            scheduled_end_at=now - timedelta(minutes=offset_minutes),
                            modality=Modality.IN_PERSON, location="R",
                        )
                        await sessions.insert_many([session])
                        await summaries.insert(
                            DailySummary(
                                owner_user_id=owner,
                                session_id=str(session.id),
                                content=f"Practice recorded for {status.value} scenario.",
                                submitted_at=now,
                                submission_status=status,
                                submitted_before_session_start=False,
                            )
                        )
                    loop = CorrectiveLoop(
                        DeterministicContentGenerator(), DeterministicContentEvaluator(), bound=3
                    )
                    workflow = ContentWorkflowService(loop, None, None, audits)
                    rollup = WeeklyRollupService(
                        summaries, sessions, users, weekly, weekly_materials, workflow, audits
                    )
                    summary = await rollup.compute(owner, trigger_instant=now)
                    self.assertEqual(summary.on_time_count, 1)
                    self.assertEqual(summary.late_count, 1)
                    self.assertEqual(summary.recorded_study_minutes, 90)
                    # Monday 00:00 in the user's tz stored as UTC
                    local_wall = summary.week_start_at.astimezone(
                        __import__("zoneinfo").ZoneInfo("Europe/Madrid")
                    )
                    self.assertEqual(local_wall.weekday(), 0)
                    self.assertEqual((local_wall.hour, local_wall.minute), (0, 0))
                    # Idempotent: a second compute returns the same persisted row
                    again = await rollup.compute(owner, trigger_instant=now)
                    self.assertEqual(str(again.id), str(summary.id))
                finally:
                    await mongo.close()

        run(scenario())


if __name__ == "__main__":
    unittest.main()