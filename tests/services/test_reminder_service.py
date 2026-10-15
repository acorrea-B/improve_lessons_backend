"""US-3 reminder service tests (T044): reminder instant is
``scheduled_start_at - 5 minutes``, the modality-specific content is
included, suppression respects the feature gate, and failures are
contained (never surfaced to the user). The emulated-SES delivery path is
replayed with a VCR cassette."""

from __future__ import annotations

import unittest
from asyncio import run
from datetime import timedelta

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import (
    AuditEventRepository,
    FeatureAvailabilityRepository,
    PlatformRepository,
    SessionRepository,
    UserRepository,
)
from app.adapters.external.notifications.localstack_email_sender import (
    InMemoryEmailSender,
    LocalStackSESEmailSender,
)
from app.core.entities.feature_availability import FeatureAvailability
from app.core.entities.session import Session
from app.core.entities.user import User
from app.core.entities.enums import CEFRLevel, Modality
from app.core.time.utc import now_utc
from app.services.reminder_service import ReminderService

from tests.commons.fixtures import mongo_available, mongo_isolated_database
from tests.commons.vcr_config import make_vcr


def build_stack(mongo):
    users = UserRepository(mongo)
    sessions = SessionRepository(mongo)
    platforms = PlatformRepository(mongo)
    audit = AuditEventRepository(mongo)
    features = FeatureAvailabilityRepository(mongo)
    return users, sessions, platforms, audit, features


async def seed_session(mongo, *, tz: str = "UTC", modality: Modality = Modality.VIRTUAL):
    users = UserRepository(mongo)
    from app.core.time.utc import now_utc

    now = now_utc()
    user = User(
        name="Reminded Learner", preferred_name="Rem", email="rem@example.com",
        cefr_level=CEFRLevel.B1, time_zone=tz, created_at=now, updated_at=now,
    )
    await users.insert_user(user)
    sessions = SessionRepository(mongo)
    session = Session(
        owner_user_id=str(user.id),
        schedule_id="schedule-r",
        # inside the reminder window [now - 5m, now + 5m)
        scheduled_start_at=now + timedelta(minutes=4),
        scheduled_end_at=now + timedelta(minutes=64),
        modality=modality,
        platform_url="https://preply.com" if modality is Modality.VIRTUAL else None,
        location="Room 7" if modality is Modality.IN_PERSON else None,
    )
    await sessions.insert_many([session])
    return user, session


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestReminderDispatch(unittest.TestCase):
    def _service(self, mongo, features_repo):
        sender = InMemoryEmailSender()
        service = ReminderService(
            SessionRepository(mongo),
            UserRepository(mongo),
            PlatformRepository(mongo),
            sender,
            AuditEventRepository(mongo),
            features_repo,
        )
        return service, sender

    def test_reminder_produced_five_minutes_before_start(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    users, sessions, platforms, audit, features = build_stack(mongo)
                    user, session = await seed_session(mongo)
                    service, sender = self._service(mongo, features)
                    count = await service.dispatch_due()
                    self.assertEqual(count, 1)
                    self.assertEqual(len(sender.sent), 1)
                    body = sender.sent[0]["body"]
                    # modality-specific content: the platform URL for virtual
                    self.assertIn("https://preply.com", body)
                    # exactly one: a second dispatch does not repeat
                    again = await service.dispatch_due()
                    self.assertEqual(again, 0)
                    self.assertEqual(len(sender.sent), 1)
                    # the session records the reminder instant
                    updated = await sessions.get(str(session.id), str(user.id))
                    self.assertIsNotNone(updated.reminder_sent_at)
                finally:
                    await mongo.close()

        run(scenario())

    def test_in_person_reminder_includes_location(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    users, sessions, platforms, audit, features = build_stack(mongo)
                    user, session = await seed_session(mongo, modality=Modality.IN_PERSON)
                    service, sender = self._service(mongo, features)
                    await service.dispatch_due()
                    self.assertEqual(len(sender.sent), 1)
                    self.assertIn("Room 7", sender.sent[0]["body"])
                finally:
                    await mongo.close()

        run(scenario())

    def test_suppressed_when_feature_disabled(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    users, sessions, platforms, audit, features = build_stack(mongo)
                    from app.core.time.utc import now_utc

                    await features.set(
                        FeatureAvailability(
                            id="reminders", enabled=False,
                            updated_at=now_utc(), updated_by="system",
                        )
                    )
                    user, session = await seed_session(mongo)
                    service, sender = self._service(mongo, features)
                    count = await service.dispatch_due()
                    self.assertEqual(count, 0)
                    self.assertEqual(sender.sent, [])
                    events = await audit.list_for_owner(str(user.id))
                    self.assertIn("reminder.suppressed", [e.event_type for e in events])
                finally:
                    await mongo.close()
        run(scenario())

    def test_delivery_failure_is_contained(self):
        async def scenario():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    users, sessions, platforms, audit, features = build_stack(mongo)

                    class FailingSender:
                        async def send(self, to, subject, body):
                            raise RuntimeError("simulated email outage")

                    service = ReminderService(
                        SessionRepository(mongo),
                        UserRepository(mongo),
                        PlatformRepository(mongo),
                        FailingSender(),
                        AuditEventRepository(mongo),
                        features,
                    )
                    user, session = await seed_session(mongo)
                    count = await service.dispatch_due()
                    self.assertEqual(count, 0)  # contained, not raised
                    events = await audit.list_for_owner(str(user.id))
                    self.assertIn("reminder.failed", [e.event_type for e in events])
                finally:
                    await mongo.close()
        run(scenario())

    def test_vcr_recorded_ses_delivery(self):
        """The LocalStack SES adapter replays the recorded emulated send."""
        from fastapi.testclient import TestClient  # noqa: F401 (import check)

        vcr = make_vcr("reminder_dispatch")
        from asyncio import run

        async def scenario():
            sender = LocalStackSESEmailSender("http://localhost:4566")
            with vcr.use_cassette("tests/vcr_cassettes/reminder_dispatch.yaml"):  # type: ignore[name-defined]
                await sender.send("rem@example.com", "Study reminder", "body")
            return True

        run(scenario())


if __name__ == "__main__":
    unittest.main()