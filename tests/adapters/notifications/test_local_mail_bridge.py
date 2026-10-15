"""LocalMailBridge unit tests (fake inner sender + fake SMTP connection
factory): SES and SMTP channels run independently with contained failures,
the starttls/login dance fires only with credentials, and each channel is
skipped/behaves identically when not configured."""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.notifications.local_mail_bridge import LocalMailBridge
from app.adapters.external.notifications.localstack_email_sender import (
    InMemoryEmailSender,
)


class RecordingSMTP:
    """Fake smtplib.SMTP connection capturing the forwarded message."""

    def __init__(self) -> None:
        self.messages: list = []
        self.tls = False
        self.credentials: tuple | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.credentials = (user, password)

    def send_message(self, message):
        self.messages.append(message)


def make_bridge(inner=None, *, factory_recorder=None, **kwargs):
    """Bridge over an in-memory inner sender with a fake SMTP factory."""
    inner = inner or InMemoryEmailSender()
    connection = RecordingSMTP()

    def factory(host: str, port: int) -> RecordingSMTP:
        if factory_recorder is not None:
            factory_recorder["last"] = (host, port)
        return connection

    bridge = LocalMailBridge(
        inner,
        smtp_host=kwargs.get("smtp_host", "smtp.internal"),
        smtp_port=kwargs.get("smtp_port", 25),
        smtp_user=kwargs.get("smtp_user", ""),
        smtp_password=kwargs.get("smtp_password", ""),
        sender_address=kwargs.get("sender_address", "noreply@local.test"),
        smtp_factory=factory,
    )
    return bridge, inner, connection


class TestLocalMailBridge(unittest.TestCase):
    def test_forwards_the_same_message_over_smtp(self):
        bridge, inner, connection = make_bridge()
        run(bridge.send("learner@example.com", "Subject here", "Body here"))
        self.assertEqual(len(inner.sent), 1)  # SES channel recorded by the inner
        self.assertEqual(len(connection.messages), 1)
        message = connection.messages[0]
        self.assertEqual(message["From"], "noreply@local.test")
        self.assertEqual(message["To"], "learner@example.com")
        self.assertEqual(message["Subject"], "Subject here")
        got_body = message.get_body(preferencelist=("plain",)).get_content().strip()
        self.assertEqual(got_body, "Body here")
        self.assertFalse(connection.tls)
        self.assertIsNone(connection.credentials)

    def test_starttls_and_login_only_with_credentials(self):
        bridge, inner, connection = make_bridge(
            smtp_user="user", smtp_password="pass"
        )
        run(bridge.send("a@example.com", "s", "b"))
        self.assertTrue(connection.tls)
        self.assertEqual(connection.credentials, ("user", "pass"))

    def test_smtp_failure_is_contained_and_does_not_break_ses(self):
        def failing_factory(host: str, port: int):
            raise ConnectionRefusedError("smtp down")

        inner = InMemoryEmailSender()
        bridge = LocalMailBridge(
            inner, smtp_host="smtp.internal", smtp_factory=failing_factory
        )
        run(bridge.send("a@example.com", "s", "b"))  # must not raise
        self.assertEqual(len(inner.sent), 1)  # SES channel unaffected

    def test_inner_failure_does_not_block_the_forward(self):
        class FailingSender:
            async def send(self, to: str, subject: str, body: str) -> None:
                raise RuntimeError("ses outage")

        bridge, _, connection = make_bridge(inner=FailingSender())
        run(bridge.send("a@example.com", "s", "b"))  # must not raise
        self.assertEqual(len(connection.messages), 1)  # forward still sent

    def test_no_smtp_host_disables_the_forward(self):
        bridge, inner, connection = make_bridge(smtp_host="")
        run(bridge.send("a@example.com", "s", "b"))
        self.assertEqual(len(inner.sent), 1)
        self.assertEqual(connection.messages, [])  # factory never called

    def test_factory_receives_the_configured_host_and_port(self):
        recorder = {}
        bridge, _, _ = make_bridge(factory_recorder=recorder, smtp_port=1025)
        run(bridge.send("a@example.com", "s", "b"))
        self.assertEqual(recorder["last"], ("smtp.internal", 1025))


if __name__ == "__main__":
    unittest.main()