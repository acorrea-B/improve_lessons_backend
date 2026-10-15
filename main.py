"""Application entry point and composition root (T010, T116).

The container in this module is the ONLY place allowed to import concrete
adapters and wire them into the port-based services (hexagonal composition
root; module boundaries in plan.md § Project Structure).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI, Request

from app.adapters.external.ai.deterministic_ai import (
    DeterministicContentEvaluator,
    DeterministicContentGenerator,
    DeterministicEmbeddingProvider,
)
from app.adapters.external.ai.local_vector_search import LocalVectorSearch
from app.adapters.external.notifications.local_mail_bridge import LocalMailBridge
from app.adapters.external.notifications.localstack_email_sender import (
    InMemoryEmailSender,
)
from app.adapters.external.auth.token_authenticator import TokenAuthenticator
from app.adapters.external.aws.secrets_manager_secret_provider import (
    SecretsManagerSecretProvider,
)
from app.adapters.external.aws.ses_email_sender import Boto3SESEmailSender
from app.adapters.persistence.mongodb.client import MongoClientWrapper
from app.adapters.persistence.mongodb.repositories import (
    AssistantThreadRepository,
    AuditEventRepository,
    ContentEvaluationRepository,
    ContentGenerationRepository,
    DailyMaterialRepository,
    FeatureAvailabilityRepository,
    IdempotencyStore,
    MonthlyMaterialRepository,
    MonthlySummaryRepository,
    PlatformRepository,
    ScheduleRepository,
    SessionRepository,
    SummaryChunkRepository,
    SummaryRepository,
    UserProfileHistoryRepository,
    UserRepository,
    WeeklyMaterialRepository,
    WeeklySummaryRepository,
)
from app.api.v1.dependencies.idempotency import IdempotencyMiddleware
from app.api.v1.error_handlers import register_error_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, aws_client_credentials, get_settings
from app.core.config.secret_provider import build_secret_provider
from app.core.ports.clock import Clock
from app.core.strategies import (
    RecommendationStrategy,
    SubmissionStatusStrategy,
    WeekBoundaryStrategy,
)
from app.services.assistant_service import AssistantService
from app.services.content.corrective_loop import CorrectiveLoop
from app.services.content.content_workflow import ContentWorkflowService
from app.services.daily_material_service import DailyMaterialService
from app.services.feature_availability_service import FeatureAvailabilityService
from app.services.history_service import HistoryService
from app.services.motivation_service import MotivationService
from app.services.platform_service import PlatformService, ScheduleService
from app.services.progress_service import ProgressService
from app.services.rag_service import RAGService
from app.services.reminder_service import ReminderService, ReminderWorker
from app.services.rollup_services import MonthlyRollupService, WeeklyRollupService
from app.services.summary_service import SummaryService
from app.services.user_service import UserService
from app.utils.logging import configure_logging, get_logger

logger = get_logger("main")


TOKEN_SIGNING_SECRET = "improve/auth/token-signing-key"

#: ``SECRETS_PROVIDER`` values routed to the real AWS Secrets Manager SDK
#: adapter (configured here, in the composition root — core never imports
#: the adapter; the import-direction lint forbids it).
AWS_SECRETSMANAGER_PROVIDERS = ("secretsmanager", "aws")


class Container:
    """Composition root: concrete adapters → ports → services."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mongo = MongoClientWrapper(settings.mongodb_uri, settings.mongodb_database)
        if settings.secrets_provider in AWS_SECRETSMANAGER_PROVIDERS:
            # Real AWS Secrets Manager SDK adapter; the client kwargs come
            # from the environment: LocalStack parameterization in
            # development, basic client (IAM) everywhere else.
            self.secret_provider = SecretsManagerSecretProvider(
                region_name=settings.aws_region,
                aws_settings=aws_client_credentials(settings.app_env),
            )
        else:
            self.secret_provider = build_secret_provider(settings)
        # Email delivery by the environment: development goes through the
        # LocalStack-parameterized SES client, non-development/test (real
        # AWS) through the basic IAM-resolved client; the unit-test
        # environment keeps the in-memory fake (no network). In development,
        # when SMTP_HOST is configured, the SES sender is decorated with a
        # bridge that forwards the same message to a real SMTP server so
        # reminders land in an actual mailbox (compose passes SMTP_HOST
        # through; empty = bridge disabled, identical behavior).
        if settings.app_env == "test":
            self.email_sender: InMemoryEmailSender | Boto3SESEmailSender = (
                InMemoryEmailSender()
            )
        else:
            ses_sender = Boto3SESEmailSender(
                sender_address=settings.ses_sender_email,
                region_name=settings.aws_region,
                aws_settings=aws_client_credentials(settings.app_env),
            )
            self.email_sender = (
                LocalMailBridge(
                    ses_sender,
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_user=settings.smtp_user,
                    smtp_password=settings.smtp_password,
                    sender_address=settings.ses_sender_email,
                )
                if settings.app_env == "development" and settings.smtp_host
                else ses_sender
            )

        # Repositories (persistence adapters)
        self.users = UserRepository(self.mongo)
        self.profile_history = UserProfileHistoryRepository(self.mongo)
        self.platforms_repo = PlatformRepository(self.mongo)
        self.schedules_repo = ScheduleRepository(self.mongo)
        self.sessions_repo = SessionRepository(self.mongo)
        self.summaries_repo = SummaryRepository(self.mongo)
        self.daily_materials_repo = DailyMaterialRepository(self.mongo)
        self.weekly_summaries_repo = WeeklySummaryRepository(self.mongo)
        self.weekly_materials_repo = WeeklyMaterialRepository(self.mongo)
        self.monthly_summaries_repo = MonthlySummaryRepository(self.mongo)
        self.monthly_materials_repo = MonthlyMaterialRepository(self.mongo)
        self.threads_repo = AssistantThreadRepository(self.mongo)
        self.generations_repo = ContentGenerationRepository(self.mongo)
        self.evaluations_repo = ContentEvaluationRepository(self.mongo)
        self.chunks_repo = SummaryChunkRepository(self.mongo)
        self.feature_availability_repo = FeatureAvailabilityRepository(self.mongo)
        self.audit_events_repo = AuditEventRepository(self.mongo)
        self.idempotency_repo = IdempotencyStore(self.mongo)

        # Clock + strategies
        self.clock: Clock = SystemClockAdapter()
        self.status_strategy = SubmissionStatusStrategy()
        self.recommendation_strategy = RecommendationStrategy()

        # AI adapters
        self.generator = DeterministicContentGenerator()
        self.evaluator = DeterministicContentEvaluator()  # separate rubric model
        self.embeddings = DeterministicEmbeddingProvider()
        self.vector_search = LocalVectorSearch(self.chunks_repo)
        self.rag = RAGService(self.embeddings, self.vector_search)

        # Services
        self.loop = CorrectiveLoop(
            self.generator, self.evaluator, bound=settings.corrective_loop_bound
        )
        self.workflow = ContentWorkflowService(
            self.loop, self.generations_repo, self.evaluations_repo, self.audit_events_repo
        )
        self.users_service = UserService(
            self.users, self.profile_history, self.audit_events_repo
        )
        self.platforms_service = PlatformService(
            self.platforms_repo, self.schedules_repo, self.audit_events_repo
        )
        self.schedules_service = ScheduleService(
            self.schedules_repo,
            self.platforms_repo,
            self.sessions_repo,
            self.users,
            self.audit_events_repo,
            self.clock,
        )
        self.summary_service = SummaryService(
            self.summaries_repo, self.sessions_repo, self.audit_events_repo, self.status_strategy
        )
        self.daily_material_service = DailyMaterialService(
            self.daily_materials_repo, self.summaries_repo, self.workflow, self.audit_events_repo
        )
        self.feature_availability_service = FeatureAvailabilityService(
            self.feature_availability_repo, self.audit_events_repo
        )
        self.weekly_rollup_service = WeeklyRollupService(
            self.summaries_repo,
            self.sessions_repo,
            self.users,
            self.weekly_summaries_repo,
            self.weekly_materials_repo,
            self.workflow,
            self.audit_events_repo,
            self.feature_availability_service,
        )
        self.monthly_rollup_service = MonthlyRollupService(
            self.weekly_summaries_repo,
            self.monthly_summaries_repo,
            self.monthly_materials_repo,
            self.users,
            self.workflow,
            self.audit_events_repo,
            self.weekly_rollup_service,
        )
        self.history_service = HistoryService(
            self.users,
            self.summary_service,
            self.daily_material_service,
            self.sessions_repo,
            self.weekly_rollup_service,
            self.monthly_rollup_service,
        )
        self.progress_service = ProgressService(
            self.users, self.summaries_repo, self.daily_materials_repo
        )
        self.motivation_service = MotivationService(
            self.users,
            self.summaries_repo,
            self.progress_service,
            self.recommendation_strategy,
            self.workflow,
            self.audit_events_repo,
        )
        self.assistant_service = AssistantService(
            self.threads_repo,
            self.users,
            self.rag,
            self.generator,
            self.feature_availability_service,
            self.audit_events_repo,
        )
        self.reminder_service = ReminderService(
            self.sessions_repo,
            self.users,
            self.platforms_repo,
            self.email_sender,
            self.audit_events_repo,
            self.feature_availability_repo,
        )
        self.reminder_worker = ReminderWorker(self.reminder_service, interval_seconds=30)

        # The API-facing namespace consumed by the endpoints.
        self.services = SimpleNamespace(
            users=self.users_service,
            platforms=self.platforms_service,
            schedules=self.schedules_service,
            summaries=self.summary_service,
            sessions_repo=self.sessions_repo,
            daily_materials=self.daily_material_service,
            weekly_rollup=self.weekly_rollup_service,
            weekly_materials=self.weekly_materials_repo,
            monthly_rollup=self.monthly_rollup_service,
            monthly_materials=self.monthly_materials_repo,
            history=self.history_service,
            assistant=self.assistant_service,
            progress=self.progress_service,
            motivation=self.motivation_service,
            feature_availability=self.feature_availability_service,
            audit_events=self.audit_events_repo,
            idempotency_store=self.idempotency_repo,
            rag=self.rag,
        )

    async def start(self) -> None:
        configure_logging()
        await self.mongo.start()
        await self.idempotency_repo.index()
        await _seed_feature_availability(self.feature_availability_repo)
        self.authenticator = TokenAuthenticator(
            await _signing_key(self.secret_provider),
            token_ttl_seconds=self.settings.auth_token_ttl_seconds,
        )
        ses_sender = (
            self.email_sender.inner
            if isinstance(self.email_sender, LocalMailBridge)
            else self.email_sender
        )
        if isinstance(ses_sender, Boto3SESEmailSender):
            # Production: a client that cannot be built fails startup (fail
            # fast). Locally: contained, the sender rebuilds the client and
            # retries on the first deliverable email.
            try:
                await ses_sender.prime()
            except Exception as exc:
                if self.settings.app_env not in ("development", "test"):
                    raise
                logger.error("ses email sender priming failed | error=%s", exc)
        self.reminder_worker.start()

    async def stop(self) -> None:
        """Graceful shutdown (T116): flush pending reminder dispatches,
        finalize in-flight corrective loops, close MongoDB."""
        try:
            await self.reminder_worker.stop()
        except Exception as exc:
            logger.error("reminder worker shutdown failed | error=%s", exc)
        # Final reminder pass so nothing enqueued right at shutdown is lost.
        try:
            await self.reminder_service.dispatch_due()
        except Exception as exc:
            logger.error("final reminder flush failed | error=%s", exc)
        try:
            await self.mongo.close()
            logger.info("shutdown complete | mongo closed")
        except Exception as exc:
            logger.error("mongo close failed | error=%s", exc)

    async def resolve_current_user_id(self, request: Request) -> str:
        """Shared with the idempotency middleware (no circular import)."""
        from app.api.v1.dependencies.auth import get_current_user_id

        return await get_current_user_id(request)


from app.core.time.clock import SystemClock as SystemClockAdapter  # noqa: E402


async def _signing_key(secret_provider) -> str:
    from app.core.config.secret_provider import EnvSecretProvider

    if isinstance(secret_provider, EnvSecretProvider):
        return await secret_provider.get_secret(TOKEN_SIGNING_SECRET)
    try:
        return await secret_provider.get_secret(TOKEN_SIGNING_SECRET)
    except Exception:
        # LocalStack not reachable: fall back to a development-only key.
        return "local-development-signing-key"


async def _seed_feature_availability(repository) -> None:
    """US-13: the global switch; missing records default to enabled."""
    for feature in (
        "reminders",
        "daily_materials",
        "weekly_summaries",
        "monthly_summaries",
        "assistant",
        "challenges",
        "recognitions",
        "progress",
    ):
        record = await repository.get(feature)
        if record is None:
            from app.core.entities.feature_availability import FeatureAvailability
            from app.core.time.utc import now_utc

            await repository.set(
                FeatureAvailability(
                    id=feature, enabled=True, updated_at=now_utc(), updated_by="system"
                )
            )


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory (T010): wires the router, logging and
    the lifespan that owns MongoDB + SecretProvider connections."""
    resolved = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = Container(resolved)
        app.state.container = container
        await container.start()
        logger.info("app started | env=%s", resolved.app_env)
        try:
            yield
        finally:
            await container.stop()

    app = FastAPI(title="improve_lessons_backend", lifespan=lifespan)
    app.include_router(api_router)
    register_error_handlers(app)
    app.add_middleware(IdempotencyMiddleware)
    return app


def _create_default_app() -> FastAPI | None:
    """Only auto-build the module-level app when configuration is present
    (unit tests build their own app via ``create_app(settings)``)."""
    try:
        return create_app()
    except Exception as exc:  # missing configuration → no default app
        logger.debug(
            "no default app instance (missing configuration?) | error=%s", exc
        )
        return None


app = _create_default_app()


def main() -> None:  # pragma: no cover
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()