"""AWS SES email sender adapter (boto3, SES API v1).

SES v1 (``boto3.client("ses")``) is intentional: LocalStack community
emulates the v1 API, and it matches the legacy httpx LocalStack sender's
action. boto3 is synchronous, so every client call runs through
``asyncio.to_thread``.

The client is initialized with the environment-decided kwargs dict from
the composition root (``aws_client_credentials(app_env)``): development
gets the LocalStack parameterization, everything else the basic client
(IAM credential chain, regional endpoint — nothing comes from Secrets
Manager).

Failures are contained: logged, never raised to callers (same policy as
``LocalStackSESEmailSender``); the client is rebuilt on the next ``send``
after a failure.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.core.ports.email_sender import EmailSender
from app.utils.logging import get_logger

logger = get_logger("notifications.email")


def _build_ses_client(region_name: str, aws_settings: dict[str, str]) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "ses",
        region_name=region_name,
        config=Config(
            retries={"max_attempts": 2}, connect_timeout=5, read_timeout=10
        ),
        **aws_settings,
    )


class Boto3SESEmailSender(EmailSender):
    """SES ``SendEmail`` via boto3; the client flavor follows the environment."""

    def __init__(
        self,
        *,
        sender_address: str = "no-reply@localhost",
        region_name: str = "us-east-1",
        aws_settings: dict[str, str] | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._sender = sender_address
        self._region_name = region_name
        self._aws_settings = dict(aws_settings or {})
        self._client_factory = client_factory or (
            lambda: _build_ses_client(self._region_name, self._aws_settings)
        )
        self._client: Any = None
        self.last_message_id: str | None = None

    async def prime(self) -> None:
        """Eagerly build the client at startup (local environments)."""
        await self._ensure_client()

    async def _ensure_client(self) -> Any:
        if self._client is None:
            self._client = await asyncio.to_thread(self._client_factory)
        return self._client

    async def send(self, to: str, subject: str, body: str) -> None:
        try:
            client = await self._ensure_client()
            response = await asyncio.to_thread(
                client.send_email,
                Source=self._sender,
                Destination={"ToAddresses": [to]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )
        except Exception as exc:
            # Contained failure: logged, never surfaces to the caller. The
            # cached client is dropped so the next send rebuilds it.
            self._client = None
            logger.error("email delivery failed | error=%s", exc)
            return
        self.last_message_id = response.get("MessageId")
        logger.info(
            "email delivered | to=%s message_id=%s", to, self.last_message_id
        )