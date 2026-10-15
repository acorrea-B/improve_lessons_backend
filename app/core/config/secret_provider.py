"""``SecretProvider`` factory (T015).

- Development / test: the LocalStack adapter (the only required adapter for
  the initial release) or the ``EnvSecretProvider`` fallback used by the
  unit-test suite.
- Production: the real adapters are a forward concern; the factory refuses
  unknown providers with an explicit configuration error.
"""

from __future__ import annotations

import os

from app.core.ports.secret_provider import SecretProvider

IN_MEMORY_SECRET_PROVIDER = "in_memory"
LOCALSTACK_SECRET_PROVIDER = "localstack"


class EnvSecretProvider(SecretProvider):
    """Reads secrets from plain environment variables (unit tests only)."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    async def get_secret(self, name: str) -> str:
        from app.core.errors import ConfigurationError

        value = self._values.get(name)
        if value is None:
            raise ConfigurationError(
                "missing_secret",
                f"Mandatory secret '{name}' is not configured.",
                details={"secret": name},
            )
        return value


class LocalStackSecretProvider(SecretProvider):
    """Reads secrets from the emulated AWS Secrets Manager (LocalStack)."""

    def __init__(self, endpoint_url: str) -> None:
        self._endpoint_url = endpoint_url

    async def get_secret(self, name: str) -> str:
        import json as _json
        from urllib.parse import urlencode, urlparse, urlunparse

        import httpx

        from app.core.errors import ConfigurationError

        # Minimal REST call instead of botocore: no AWS SDK dependency in
        # this package, and the LocalStack emulation covers the AWS v4
        # signature required by the real client only for production.
        parsed = urlparse(self._endpoint_url)
        path = f"{parsed.path}/".rstrip("/") + f"/{name}"
        url = urlunparse((parsed.scheme, parsed.netloc, path, "", f"?{urlencode({'get': 'value'})}", ""))
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url, headers={"x-amz-target": ""})
        if response.status_code != 200:
            raise ConfigurationError(
                "missing_secret",
                f"Mandatory secret '{name}' is not available "
                f"(provider returned {response.status_code}).",
                details={"secret": name, "provider_status": response.status_code},
            )
        document = _json.loads(response.text)
        if document.get("SecretString") is None:
            raise ConfigurationError(
                "missing_secret",
                f"Mandatory secret '{name}' has no string value.",
                details={"secret": name},
            )
        return str(document["SecretString"])


def build_secret_provider(settings) -> SecretProvider:
    """Factory resolved from environment / Settings (T015)."""
    provider = settings.secrets_provider
    if provider == LOCALSTACK_SECRET_PROVIDER:
        if not settings.secrets_endpoint_url:
            raise ValueError(
                "missing_configuration: SECRETS_ENDPOINT_URL is mandatory when "
                "SECRETS_PROVIDER=localstack"
            )
        return LocalStackSecretProvider(settings.secrets_endpoint_url)
    if provider == IN_MEMORY_SECRET_PROVIDER:
        return EnvSecretProvider(
            {"improve/auth/token-signing-key": os.getenv("TOKEN_SIGNING_KEY", "dev-only")}
        )
    raise ValueError(f"invalid_configuration: unknown SECRETS_PROVIDER '{provider}'")