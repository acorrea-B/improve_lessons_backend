"""Application configuration (T015).

Business logic reads configuration only through the ``SecretProvider`` /
``Settings`` objects defined here; no module imports the AWS SDK (or any
Secrets Manager client) directly (research.md § 6).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.core.errors import ConfigurationError

#: Feature availability defaults for the initial release (US-13, A-8).
FEATURES: tuple[str, ...] = (
    "reminders",
    "daily_materials",
    "weekly_summaries",
    "monthly_summaries",
    "assistant",
    "challenges",
    "recognitions",
    "progress",
)

#: Bound of the content corrective loop (A-10, default 3 evaluations).
DEFAULT_CORRECTIVE_LOOP_BOUND = 3


@dataclass
class Settings:
    """Process-wide configuration read from environment variables."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    mongodb_uri: str = field(default_factory=lambda: os.getenv("MONGODB_URI", ""))
    mongodb_database: str = field(
        default_factory=lambda: os.getenv("MONGODB_DATABASE", "improve_lessons")
    )
    secrets_provider: str = field(
        default_factory=lambda: os.getenv("SECRETS_PROVIDER", "localstack")
    )
    secrets_endpoint_url: str = field(
        default_factory=lambda: os.getenv("SECRETS_ENDPOINT_URL", "")
    )
    corrective_loop_bound: int = field(
        default_factory=lambda: int(
            os.getenv("CORRECTIVE_LOOP_BOUND", str(DEFAULT_CORRECTIVE_LOOP_BOUND))
        )
    )
    # Authentication token TTL in seconds (deferred mechanism placeholder).
    auth_token_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800"))
    )
    # AWS region for the real AWS SDK adapters (SES, Secrets Manager).
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    ses_sender_email: str = field(
        default_factory=lambda: os.getenv("SES_SENDER_EMAIL", "no-reply@localhost")
    )
    # Real-email bridge (development only): SMTP_HOST="" disables the
    # LocalMailBridge. smtp_user/smtp_password enable STARTTLS+login for
    # servers that require auth (an internal postfix usually does not).
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "25")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))

    def validate_mandatory(self) -> "Settings":
        """Refuse to start when mandatory configuration is missing."""
        missing = [
            name
            for name in ("mongodb_uri",)
            if not getattr(self, name)
        ]
        if self.secrets_provider == "localstack" and not self.secrets_endpoint_url:
            missing.append("secrets_endpoint_url")
        if missing:
            raise ConfigurationError(
                "missing_configuration",
                f"Mandatory configuration is missing: {', '.join(missing)}.",
                details={"missing": missing},
            )
        if self.mongodb_database.strip() == "":
            raise ConfigurationError(
                "missing_configuration", "MONGODB_DATABASE must not be empty."
            )
        return self


def get_settings() -> Settings:
    return Settings().validate_mandatory()


#: The AWS client parameterization for the local environment (LocalStack
#: emulator) lives here, as the single source: the documented LocalStack
#: community default pair — which grants nothing beyond that instance —
#: plus the emulator edge URL (override with AWS_ENDPOINT_URL, e.g. the
#: docker service name). Production never receives this dict: basic client,
#: no explicit credentials (IAM chain) and no endpoint override.
LOCALSTACK_AWS_CREDENTIALS = {
    "aws_access_key_id": "test",
    "aws_secret_access_key": "test",
    "endpoint_url": os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
}


def aws_client_credentials(app_env: str) -> dict[str, str]:
    """boto3 client kwargs decided by the environment, NOT by the URL.

    Development gets the full LocalStack parameterization
    (``LOCALSTACK_AWS_CREDENTIALS``); every other environment gets the basic
    client: the dict goes empty — production resolves credentials via IAM
    and the regional endpoint. Any AWS SDK client initializes as
    ``boto3.client(<service>, **aws_client_credentials(app_env))``.
    """
    if app_env == "development":
        return dict(LOCALSTACK_AWS_CREDENTIALS)
    return {}