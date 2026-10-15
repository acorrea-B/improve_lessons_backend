"""MongoDB async client wrapper (T017).

Built on Pymongo's native async API (``AsyncMongoClient``) — NOT Motor
(research.md § 2). The wrapper raises on startup when the connection
cannot be established; no module outside ``app/adapters/persistence/`` is
allowed to touch the client.
"""

from __future__ import annotations

from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.errors import ConfigurationError, ServiceUnavailableError
from app.core.time.utc import now_utc
from app.utils.logging import get_logger

logger = get_logger("persistence.mongodb")


class MongoClientWrapper:
    """Owns the single async MongoDB connection for the process."""

    def __init__(
        self,
        uri: str,
        database: str,
        *,
        server_selection_timeout_ms: int = 10_000,
    ) -> None:
        if not uri:
            raise ConfigurationError(
                "missing_configuration",
                "MONGODB_URI is mandatory.",
                details={"field": "mongodb_uri"},
            )
        if not database:
            raise ConfigurationError(
                "missing_configuration",
                "MONGODB_DATABASE is mandatory.",
                details={"field": "mongodb_database"},
            )
        self._client: AsyncMongoClient = AsyncMongoClient(
            uri, serverSelectionTimeoutMS=server_selection_timeout_ms
        )
        self._database_name = database
        self._started = False

    def database(self) -> AsyncDatabase:
        return self._client[self._database_name]

    @property
    def database_name(self) -> str:
        return self._database_name

    async def start(self) -> None:
        """Verify connectivity; raises ServiceUnavailableError on failure."""
        try:
            await self._client.admin.command("ping")
        except Exception as exc:  # PyMongoError / network errors
            raise ServiceUnavailableError(
                "database_unavailable",
                f"Cannot connect to MongoDB: {exc}",
                retry_after_seconds=5,
            ) from exc
        self._started = True
        await self._ensure_indexes()

    async def close(self) -> None:
        await self._client.close()
        self._started = False

    async def _ensure_indexes(self) -> None:
        """Index definitions (data-model.md § Indexes, T019)."""
        database = self.database()
        await database["users"].create_index("email", unique=True)
        await database["schedules"].create_index(
            "owner_user_id", name="owner_user_id_scope"
        )
        await database["sessions"].create_index(
            "owner_user_id", name="owner_user_id_scope"
        )
        await database["sessions"].create_index(
            [("schedule_id", 1), ("scheduled_start_at", 1)],
            name="schedule_start_unique",
            unique=True,
        )
        await database["sessions"].create_index(
            [("scheduled_start_at", 1), ("reminder_sent_at", 1)],
            name="reminder_scan",
        )
        await database["daily_summaries"].create_index(
            "session_id", unique=True, name="one_summary_per_session"
        )
        await database["daily_summaries"].create_index(
            [("owner_user_id", 1), ("submitted_at", 1)]
        )
        await database["daily_materials"].create_index(
            "summary_id", unique=True, name="one_material_per_summary"
        )
        await database["daily_materials"].create_index(
            [("owner_user_id", 1), ("approved_at", 1)]
        )
        await database["weekly_summaries"].create_index(
            [("owner_user_id", 1), ("week_start_at", 1)],
            unique=True,
            name="one_weekly_summary_per_period",
        )
        await database["monthly_summaries"].create_index(
            [("owner_user_id", 1), ("month_start_at", 1)],
            unique=True,
            name="one_monthly_summary_per_period",
        )
        await database["summary_chunks"].create_index(
            [("owner_user_id", 1), ("is_obsolete", 1)]
        )
        await database["idempotency_keys"].create_index(
            [("expires_at", 1)], expireAfterSeconds=0, name="idempotency_ttl"
        )
        for collection in (
            "users_profile_history",
            "external_learning_platforms",
            "assistant_threads",
            "content_generations",
            "content_evaluations",
            "weekly_materials",
            "monthly_materials",
            "feature_availability_config",
            "audit_events",
        ):
            await database[collection].create_index("owner_user_id")

    # -- utility used by the test fixtures -----------------------------------
    async def drop_database(self, name: str) -> None:
        await self._client.drop_database(name)


def as_bson_ready(document: dict[str, Any]) -> dict[str, Any]:
    """Last-chance guard: no naive datetimes may reach BSON conversion."""
    for key, value in document.items():
        if isinstance(value, type(now_utc())) and value.tzinfo is None:
            raise ConfigurationError(
                "naive_datetime_rejected",
                f"Field '{key}' holds a naive datetime; UTC invariant violated.",
            )
    return document