"""Monthly rollup integration (T074): the calendar month in the user's tz,
aggregating the persisted weekly rows, with the approval-gated material."""

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
    MonthlyMaterialRepository,
    MonthlySummaryRepository,
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
from app.services.rollup_services import MonthlyRollupService, WeeklyRollupService

from tests.commons.fixtures import mongo_available, mongo_isolated_database


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestMonthlyRollup(unittest.TestCase):
    def test_monthly_counts_from_weeks_and_material(self):
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
                    monthly = MonthlySummaryRepository(mongo)
                    monthly_materials = MonthlyMaterialRepository(mongo)
                    audits = AuditEventRepository(mongo)
                    now = now_utc()
                    user = User(
                        name="Monthly", email="monthly@example.com",
                        cefr_level=CEFRLevel.B1, time_zone="UTC",
                        created_at=now, updated_at=now,
                    )
                    await users.insert_user(user)
                    owner = str(user.id)
                    for index in range(2):
                        session = Session(
                            owner_user_id=owner,
                            schedule_id=f"sch-{index}",
                            scheduled_start_at=now - timedelta(minutes=100 - index * 5),
                            scheduled_end_at=now - timedelta(minutes=70 - index * 5),
                            modality=Modality.IN_PERSON, location="R",
                        )
                        await sessions.insert_many([session])
                        await summaries.insert(
                            DailySummary(
                                owner_user_id=owner,
                                session_id=str(session.id),
                                content=f"Practice {index}.",
                                submitted_at=now - timedelta(minutes=70 - index * 5),
                                submission_status=SubmissionStatus.ON_TIME,
                                submitted_before_session_start=False,
                            )
                        )
                    loop = CorrectiveLoop(
                        DeterministicContentGenerator(), DeterministicContentEvaluator(), bound=3
                    )
                    workflow = ContentWorkflowService(loop, None, None, audits)
                    weekly_rollup = WeeklyRollupService(
                        summaries, sessions, users, weekly, weekly_materials, workflow, audits
                    )
                    monthly_rollup = MonthlyRollupService(
                        weekly, monthly, monthly_materials, users, workflow, audits,
                        weekly_rollup,
                    )
                    result = await monthly_rollup.compute(owner, trigger_instant=now)
                    self.assertEqual(result.on_time_count, 2)
                    # a month with no submissions still returns a summary
                    empty_user = User(
                        name="Empty", email="empty@example.com",
                        cefr_level=CEFRLevel.A1, time_zone="UTC",
                        created_at=now, updated_at=now,
                    )
                    await users.insert_user(empty_user)
                    rollup_empty = await monthly_rollup.compute(str(empty_user.id), trigger_instant=now)
                    self.assertEqual(rollup_empty.on_time_count, 0)
                finally:
                    await mongo.close()

        run(scenario())


if __name__ == "__main__":
    unittest.main()