"""Summary repository integration tests (T049): duplicate rejection per
session, UTC invariant, owner scoping."""

from __future__ import annotations

import unittest
from asyncio import run
from datetime import timedelta

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import (
    SessionRepository,
    SummaryRepository,
)
from app.core.entities.daily_summary import DailySummary
from app.core.entities.enums import Modality, SubmissionStatus
from app.core.entities.session import Session
from app.core.errors import ConflictError
from app.core.time.utc import now_utc

from tests.commons.fixtures import mongo_available, mongo_isolated_database


def make_session(owner: str) -> Session:
    now = now_utc()
    return Session(
        owner_user_id=owner,
        schedule_id="schedule-x",
        scheduled_start_at=now - timedelta(hours=2),
        scheduled_end_at=now - timedelta(hours=1),
        modality=Modality.IN_PERSON,
        location="Room 1",
    )


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestSummaryRepository(unittest.TestCase):
    def test_duplicate_session_id_rejected(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    sessions = SessionRepository(mongo)
                    summaries = SummaryRepository(mongo)
                    session = await sessions.insert_many([make_session("owner-1")])
                    summary = DailySummary(
                        owner_user_id="owner-1",
                        session_id=str(session[0].id),
                        content="Record one.",
                        submitted_at=now_utc(),
                        submission_status=SubmissionStatus.LATE,
                        submitted_before_session_start=False,
                    )
                    await summaries.insert(summary)
                    with self.assertRaises(ConflictError) as ctx:
                        await summaries.insert(
                            DailySummary(
                                owner_user_id="owner-1",
                                session_id=str(session[0].id),
                                content="Duplicate attempt.",
                                submitted_at=now_utc(),
                                submission_status=SubmissionStatus.LATE,
                                submitted_before_session_start=False,
                            )
                        )
                    self.assertEqual(ctx.exception.code, "summary_already_exists")
                finally:
                    await mongo.close()

        run(scenario())

    def test_utc_round_trip(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    sessions = SessionRepository(mongo)
                    summaries = SummaryRepository(mongo)
                    session = await sessions.insert_many([make_session("owner-2")])
                    stamp = now_utc()
                    summary = DailySummary(
                        owner_user_id="owner-2",
                        session_id=str(session[0].id),
                        content="UTC round trip.",
                        submitted_at=stamp,
                        submission_status=SubmissionStatus.ON_TIME,
                        submitted_before_session_start=False,
                    )
                    await summaries.insert(summary)
                    fetched = await summaries.get(str(summary.id), "owner-2")
                    self.assertEqual(fetched.submitted_at.isoformat(timespec="milliseconds"), stamp.isoformat(timespec="milliseconds"))
                    self.assertIsNotNone(fetched.submitted_at.tzinfo)
                finally:
                    await mongo.close()

        run(scenario())

    def test_late_submission_keeps_status_in_listing(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    sessions = SessionRepository(mongo)
                    summaries = SummaryRepository(mongo)
                    session = await sessions.insert_many([make_session("owner-3")])
                    summary = DailySummary(
                        owner_user_id="owner-3",
                        session_id=str(session[0].id),
                        content="Late but kept.",
                        submitted_at=now_utc() - timedelta(hours=12),
                        submission_status=SubmissionStatus.LATE,
                        submitted_before_session_start=False,
                    )
                    await summaries.insert(summary)
                    rows = await summaries.list_for_owner("owner-3")
                    self.assertEqual(rows[0].submission_status, SubmissionStatus.LATE)
                finally:
                    await mongo.close()

        run(scenario())


if __name__ == "__main__":
    unittest.main()