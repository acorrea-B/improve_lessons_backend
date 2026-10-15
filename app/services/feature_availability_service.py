"""Feature availability service (T105, US-13, A-8).

A single global on/off switch per feature for the initial release; missing
records default to ENABLED. Per-user overrides are a forward concern
(FR-081).
"""

from __future__ import annotations

from app.core.entities.feature_availability import AuditEvent, FeatureAvailability
from app.core.errors import FeatureUnavailableError
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.feature_availability_repository import FeatureAvailabilityRepository
from app.utils.logging import report_info

_KNOWN_FEATURES = (
    "reminders",
    "daily_materials",
    "weekly_summaries",
    "monthly_summaries",
    "assistant",
    "challenges",
    "recognitions",
    "progress",
)


class FeatureAvailabilityService:
    def __init__(
        self,
        repository: FeatureAvailabilityRepository,
        audit_events: AuditEventRepository | None = None,
    ) -> None:
        self._repository = repository
        self._audit = audit_events

    async def is_enabled(self, feature: str) -> bool:
        record = await self._repository.get(feature)
        return True if record is None else bool(record.enabled)

    async def ensure_enabled(self, feature: str) -> None:
        if not await self.is_enabled(feature):
            raise FeatureUnavailableError(feature)

    async def set_state(self, feature: str, enabled: bool, updated_by: str) -> FeatureAvailability:
        from app.core.time.utc import now_utc

        record = FeatureAvailability(
            id=feature,  # the feature name doubles as _id
            enabled=enabled,
            updated_at=now_utc(),
            updated_by=updated_by,
        )
        await self._repository.set(record)
        report_info(
            "feature_availability.updated",
            "feature state changed",
            feature=feature,
            enabled=enabled,
        )
        if self._audit is not None:
            await self._audit.insert(
                AuditEvent(
                    owner_user_id=None,
                    event_type="feature_availability.enabled"
                    if enabled
                    else "feature_availability.disabled",
                    payload={"feature": feature, "updated_by": updated_by},
                )
            )
        return record

    async def list_state(self) -> dict[str, bool]:
        records = {record.id: bool(record.enabled) for record in await self._repository.list_all()}
        return {feature: records.get(feature, True) for feature in _KNOWN_FEATURES}