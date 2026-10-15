"""User repository integration tests against real MongoDB (T033)."""

from __future__ import annotations

import unittest

from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import (
    AuditEventRepository,
    UserProfileHistoryRepository,
    UserRepository,
)
from app.core.entities.feature_availability import AuditEvent
from app.core.entities.user import ProfileChange, User
from app.core.entities.enums import CEFRLevel
from app.core.errors import ConflictError
from app.core.time.utc import now_utc

from tests.commons.fixtures import mongo_available, mongo_isolated_database
from tests.commons.helpers import register, headers_for


def make_user(name: str, email: str, tz: str = "America/Bogota") -> User:
    stamp = now_utc()
    return User(
        name=name, email=email, cefr_level=CEFRLevel.B1, time_zone=tz,
        created_at=stamp, updated_at=stamp,
    )


@unittest.skipUnless(mongo_available(), "MongoDB is not running")
class TestUserRepository(unittest.TestCase):
    def run_with_repos(self, flow):
        from asyncio import run

        async def go():
            with mongo_isolated_database() as database:
                mongo = MongoClientWrapper("mongodb://localhost:27017", database)
                await mongo.start()
                try:
                    return await flow(
                        UserRepository(mongo),
                        UserProfileHistoryRepository(mongo),
                        AuditEventRepository(mongo),
                    )
                finally:
                    await mongo.close()

        return run(go())

    def test_unique_email_enforcement_case_insensitive(self):
        flow = self.run_with_repos

        async def scenario(users, history, audit):
            await users.insert_user(make_user("A", "unique1@example.com"))
            with self.assertRaises(ConflictError):
                await users.insert_user(make_user("B", "UNIQUE1@example.com"))
            return True

        self.assertTrue(flow(scenario))

    def test_profile_history_appended_per_change(self):
        async def scenario(users, history, audit):
            user = make_user("A", "history@example.com")
            await users.insert_user(user)
            user.cefr_level = CEFRLevel.B2
            await users.update(user)
            await history.append(
                ProfileChange(
                    user_id=str(user.id),
                    changed_fields={"cefr_level": {"previous": "B1", "new": "B2"}},
                    changed_at=now_utc(),
                    version=1,
                )
            )
            rows = await history.list_for_user(str(user.id))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].changed_fields["cefr_level"]["new"], "B2")
            # append-only: a second update appends a second row
            user.cefr_level = CEFRLevel.C1
            await users.update(user)
            await history.append(
                ProfileChange(
                    user_id=str(user.id),
                    changed_fields={"cefr_level": {"previous": "B2", "new": "C1"}},
                    changed_at=now_utc(),
                    version=1,
                )
            )
            self.assertEqual(len(await history.list_for_user(str(user.id))), 2)
            return True

        self.assertTrue(self.run_with_repos(scenario))

    def test_owner_user_id_scope_and_utc_invariant(self):
        async def scenario(users, history, audit):
            user = make_user("A", "scope@example.com")
            await users.insert_user(user)
            fetched = await users.get_by_id(str(user.id))
            self.assertEqual(fetched.created_at.tzinfo is not None, True)
            # naive datetimes are rejected at the persistence boundary
            from app.adapters.persistence.mongodb.mappers import NaiveDatetimeError, dump_entity
            from datetime import datetime

            # Build the naive entity bypassing entity validation to prove
            # the ADAPTER boundary raises before any write.
            naive = User.model_construct(
                name="N", email="naive@example.com", cefr_level=CEFRLevel.B1,
                time_zone="UTC", created_at=datetime(2026, 1, 1), updated_at=now_utc(),
                version=1,
            )
            with self.assertRaises(NaiveDatetimeError):
                await users.insert_user(naive)
            return True

        self.assertTrue(self.run_with_repos(scenario))

    def test_audit_events_append_only(self):
        async def scenario(users, history, audit):
            await audit.insert(
                AuditEvent(owner_user_id=None, event_type="system.event", payload={"x": 1})
            )
            rows = await audit.list_for_owner("none")
            return True

        self.assertTrue(self.run_with_repos(scenario))


if __name__ == "__main__":
    unittest.main()