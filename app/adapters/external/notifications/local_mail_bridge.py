"""Development-only mail bridge: real email delivery over SMTP.

LocalStack community SES accepts ``SendEmail`` but never delivers to a
real mailbox (real SMTP relay delivery is a paid tier). ``LocalMailBridge``
decorates the ``EmailSender`` port: it first runs the inner sender — the
real SES path stays intact for functional tests — and then forwards the
same message to a real SMTP server (internal postfix/mailutils), so
reminders produced in local functional tests land in an actual inbox.

Wired only by the composition root in development when ``SMTP_HOST`` is
configured. Failures are independent and contained per channel: SES
failure does not block the forward, an SMTP failure is logged and never
surfaces (the SES side already has its own contained policy).
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from app.core.ports.email_sender import EmailSender
from app.utils.logging import get_logger

logger = get_logger("notifications.email")


def _open_smtp(host: str, port: int) -> Any:
    import smtplib

    return smtplib.SMTP(host, port, timeout=5)


class LocalMailBridge(EmailSender):
    """SES (inner) + real SMTP forward, with independent contained failures."""

    def __init__(
        self,
        inner: EmailSender,
        *,
        smtp_host: str,
        smtp_port: int = 25,
        smtp_user: str = "",
        smtp_password: str = "",
        sender_address: str = "no-reply@localhost",
        smtp_factory: Callable[[str, int], Any] | None = None,
    ) -> None:
        self.inner = inner
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._sender = sender_address
        self._smtp_factory = smtp_factory or (lambda host, port: _open_smtp(host, port))

    async def send(self, to: str, subject: str, body: str) -> None:
        # Channel 1 — SES via the inner sender: contained here too, so any
        # SES failure (its own contained policy or an unexpected raise) can
        # never block the real-mail forward.
        try:
            await self.inner.send(to, subject, body)
        except Exception as exc:
            logger.error("email delivery failed | to=%s channel=ses error=%s", to, exc)
        # Channel 2 — real SMTP forward: contained independently, so the
        # email is not lost when the SES leg fails and vice versa.
        if not self._smtp_host:
            return
        try:
            await asyncio.to_thread(self._forward_smtp, to, subject, body)
        except Exception as exc:
            logger.error("email forward failed | to=%s channel=smtp error=%s", to, exc)

    def _forward_smtp(self, to: str, subject: str, body: str) -> None:
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        # The with-block closes the connection on success or failure.
        with self._smtp_factory(self._smtp_host, self._smtp_port) as connection:
            if self._smtp_user:
                connection.starttls()
                connection.login(self._smtp_user, self._smtp_password)
            connection.send_message(message)
        logger.info("email delivered | to=%s channel=smtp host=%s", to, self._smtp_host)