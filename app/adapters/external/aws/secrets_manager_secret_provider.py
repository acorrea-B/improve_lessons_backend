"""Real AWS Secrets Manager ``SecretProvider`` adapter (boto3).

The client flavor is injected by the composition root as
``aws_client_credentials(app_env)`` — full LocalStack parameterization in
development, empty dict (basic client: IAM chain, regional endpoint) in
every other environment. The boto3 import is function-level: the SDK must
stay out of the core layers.
"""

from __future__ import annotations

import asyncio

from app.core.errors import ConfigurationError
from app.core.ports.secret_provider import SecretProvider
from app.utils.logging import get_logger

logger = get_logger("secrets.aws")


class SecretsManagerSecretProvider(SecretProvider):
    """``SecretProvider`` backed by the AWS Secrets Manager SDK client."""

    def __init__(self, region_name: str, aws_settings: dict[str, str] | None = None) -> None:
        self._region_name = region_name
        self._aws_settings = dict(aws_settings or {})
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "secretsmanager",
                region_name=self._region_name,
                config=Config(
                    retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10
                ),
                **self._aws_settings,
            )
        return self._client

    async def get_secret(self, name: str) -> str:
        try:
            response = await asyncio.to_thread(
                self._get_client().get_secret_value, SecretId=name
            )
        except ConfigurationError:
            raise
        except Exception as exc:
            raise ConfigurationError(
                "missing_secret",
                f"Secret '{name}' could not be retrieved from the secrets "
                "provider.",
                details={"secret": name},
            ) from exc
        secret_string = response.get("SecretString")
        if secret_string is None:
            raise ConfigurationError(
                "missing_secret",
                f"Secret '{name}' has no string value.",
                details={"secret": name},
            )
        return str(secret_string)