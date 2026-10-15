"""Email sender adapters (T021, research.md § 6).

- ``InMemoryEmailSender``: the default in development and tests — records
  rendered messages in memory so the suite needs no network access.
- ``LocalStackSESEmailSender``: renders to the emulated SES via httpx when
  a real(ish) outbound path is wanted locally.
"""

from __future__ import annotations

from app.utils.logging import get_logger

logger = get_logger("notifications.email")


class InMemoryEmailSender:
    """Fake ``EmailSender`` — records every message for assertions."""

    def __init__(self) -> None:
        # list of {"to", "subject", "body", "sent_at"}
        self.sent: list[dict] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        from app.core.time.utc import now_utc

        self.sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
                "sent_at": now_utc(),
            }
        )
        logger.info("email recorded | to=%s subject=%s", to, subject)


class LocalStackSESEmailSender:
    """Emulated SES delivery via the LocalStack REST edge (no AWS SDK)."""

    def __init__(self, endpoint_url: str, sender_address: str = "no-reply@localhost") -> None:
        self._endpoint_url = endpoint_url.rstrip("/")
        self._sender = sender_address

    async def send(self, to: str, subject: str, body: str) -> None:
        import httpx

        from app.core.errors import ServiceUnavailableError

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self._endpoint_url}/",
                    json={
                        "Action": "SendEmail",
                        "Source": self._sender,
                        "Destination.ToAddresses.member.1": to,
                        "Message.Subject.Data": subject,
                        "Message.Body.Text.Data": body,
                        "Version": "2010-12-01",
                    },
                )
        except Exception as exc:
            # Contained failure: logged, never surfaces unapproved error text
            # to the user (constitution principle X).
            logger.error("email delivery failed | error=%s", exc)
            return
        if response.status_code not in (200, 429):
            logger.error(
                "email delivery failed | provider_status=%s", response.status_code
            )
            return
        logger.info("email delivered | to=%s", to)