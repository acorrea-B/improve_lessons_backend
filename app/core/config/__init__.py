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

    def validate_mandatory(self) -> "Settings":
        """Refuse to start when mandatory configuration is missing."""
        missing = [
            name
            for name in ("mongodb_uri", "secrets_endpoint_url")
            if not getattr(self, name)
        ]
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