"""MongoDB repository adapters (T019) implementing the ports in
``app/core/ports``. One adapter per port; every query is owner-scoped."""

from app.adapters.persistence.mongodb.repositories.assistant_thread_repository import (
    AssistantThreadRepository,
)
from app.adapters.persistence.mongodb.repositories.audit_event_repository import (
    AuditEventRepository,
)
from app.adapters.persistence.mongodb.repositories.base import MongoRepository
from app.adapters.persistence.mongodb.repositories.content_evaluation_repository import (
    ContentEvaluationRepository,
)
from app.adapters.persistence.mongodb.repositories.content_generation_repository import (
    ContentGenerationRepository,
)
from app.adapters.persistence.mongodb.repositories.daily_material_repository import (
    DailyMaterialRepository,
)
from app.adapters.persistence.mongodb.repositories.feature_availability_repository import (
    FeatureAvailabilityRepository,
)
from app.adapters.persistence.mongodb.repositories.idempotency_store import (
    IdempotencyStore,
)
from app.adapters.persistence.mongodb.repositories.monthly_material_repository import (
    MonthlyMaterialRepository,
)
from app.adapters.persistence.mongodb.repositories.monthly_summary_repository import (
    MonthlySummaryRepository,
)
from app.adapters.persistence.mongodb.repositories.platform_repository import (
    PlatformRepository,
)
from app.adapters.persistence.mongodb.repositories.schedule_repository import (
    ScheduleRepository,
)
from app.adapters.persistence.mongodb.repositories.session_repository import (
    SessionRepository,
)
from app.adapters.persistence.mongodb.repositories.summary_chunk_repository import (
    SummaryChunkRepository,
)
from app.adapters.persistence.mongodb.repositories.summary_repository import (
    SummaryRepository,
)
from app.adapters.persistence.mongodb.repositories.user_profile_history_repository import (
    UserProfileHistoryRepository,
)
from app.adapters.persistence.mongodb.repositories.user_repository import (
    UserRepository,
)
from app.adapters.persistence.mongodb.repositories.weekly_material_repository import (
    WeeklyMaterialRepository,
)
from app.adapters.persistence.mongodb.repositories.weekly_summary_repository import (
    WeeklySummaryRepository,
)

__all__ = [
    "AssistantThreadRepository",
    "AuditEventRepository",
    "ContentEvaluationRepository",
    "ContentGenerationRepository",
    "DailyMaterialRepository",
    "FeatureAvailabilityRepository",
    "IdempotencyStore",
    "MongoRepository",
    "MonthlyMaterialRepository",
    "MonthlySummaryRepository",
    "PlatformRepository",
    "ScheduleRepository",
    "SessionRepository",
    "SummaryChunkRepository",
    "SummaryRepository",
    "UserProfileHistoryRepository",
    "UserRepository",
    "WeeklyMaterialRepository",
    "WeeklySummaryRepository",
]