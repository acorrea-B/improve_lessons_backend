"""Boto3SESEmailSender unit tests (fake AWS client injected through the
``client_factory`` seam): payload shape, client caching, reset-after-failure
and the contained-failure policy."""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.aws.ses_email_sender import Boto3SESEmailSender


class RecordingClient:
    """Fake SES v1 client capturing the last SendEmail call."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self._fail = fail

    def send_email(self, **kwargs):
        if self._fail:
            raise RuntimeError("ses unavailable")
        self.calls.append(kwargs)
        return {"MessageId": "msg-123"}


class TestBoto3SESEmailSender(unittest.TestCase):
    def test_send_builds_expected_v1_payload(self):
        clients: list[RecordingClient] = []

        def factory() -> RecordingClient:
            client = RecordingClient()
            clients.append(client)
            return client

        sender = Boto3SESEmailSender(
            sender_address="no-reply@localhost", client_factory=factory
        )
        run(sender.send("you@example.com", "Subject here", "Body here"))
        self.assertEqual(len(clients), 1)
        call = clients[0].calls[0]
        self.assertEqual(call["Source"], "no-reply@localhost")
        self.assertEqual(call["Destination"], {"ToAddresses": ["you@example.com"]})
        self.assertEqual(
            call["Message"]["Subject"], {"Data": "Subject here", "Charset": "UTF-8"}
        )
        self.assertEqual(call["Message"]["Body"]["Text"]["Data"], "Body here")
        self.assertEqual(sender.last_message_id, "msg-123")

    def test_client_is_cached_across_sends(self):
        counter = {"built": 0}

        def factory() -> RecordingClient:
            counter["built"] += 1
            return RecordingClient()

        sender = Boto3SESEmailSender(client_factory=factory)
        run(sender.send("a@example.com", "s1", "b1"))
        run(sender.send("b@example.com", "s2", "b2"))
        self.assertEqual(counter["built"], 1)

    def test_send_failure_is_contained_and_client_is_reset(self):
        counter = {"built": 0}

        def factory() -> RecordingClient:
            counter["built"] += 1
            return RecordingClient(fail=counter["built"] == 1)

        sender = Boto3SESEmailSender(client_factory=factory)
        run(sender.send("a@example.com", "s", "b"))  # fails, contained
        self.assertIsNone(sender.last_message_id)
        run(sender.send("a@example.com", "s", "b"))  # retry: new client succeeds
        self.assertEqual(counter["built"], 2)
        self.assertEqual(sender.last_message_id, "msg-123")

    def test_prime_eagerly_builds_the_client(self):
        counter = {"built": 0}

        def factory() -> RecordingClient:
            counter["built"] += 1
            return RecordingClient()

        sender = Boto3SESEmailSender(client_factory=factory)
        run(sender.prime())
        self.assertEqual(counter["built"], 1)

    def test_default_factory_targets_the_ses_v1_client(self):
        # Default client_factory (no seam) is the real boto3 builder; only
        # assert it is wired — boto3 may be absent in some unit-test envs.
        sender = Boto3SESEmailSender(aws_settings={"endpoint_url": "http://ls:4566"})
        self.assertIsNotNone(sender._client_factory)


if __name__ == "__main__":
    unittest.main()