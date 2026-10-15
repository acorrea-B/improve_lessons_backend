"""Integration tests for the real AWS SDK path against the LocalStack
emulation (secretsmanager + ses services): the SecretsManager provider
reads the seeded dummy inventory (no credentials carried in secrets) and
``Boto3SESEmailSender`` delivers an email through ``send_email`` with the
LocalStack default credentials. Skipped when the LocalStack edge
(localhost:4566) is unreachable."""

from __future__ import annotations

import asyncio
import socket
import unittest

from app.adapters.external.aws.ses_email_sender import Boto3SESEmailSender
from app.adapters.external.aws.secrets_manager_secret_provider import (
    SecretsManagerSecretProvider,
)
from app.core.config import aws_client_credentials

LOCALSTACK = "http://localhost:4566"
SENDER = "no-reply@local.test"


def _reachable(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except OSError:
        return False


def _bootstrap_ses() -> None:
    """LocalStack community SES enforces verified identities; make sure the
    test sender is one (idempotent, mirrors the init script)."""
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "ses",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        endpoint_url=LOCALSTACK,
        config=Config(retries={"max_attempts": 2}),
    )
    asyncio.run(
        asyncio.to_thread(client.verify_email_identity, EmailAddress=SENDER)
    )


@unittest.skipUnless(_reachable(4566), "LocalStack is not running (compose up localstack)")
class TestAwsSdkAgainstLocalStack(unittest.TestCase):
    def setUp(self):
        if not _reachable(4566):
            raise unittest.SkipTest("LocalStack is not running")

    def test_secrets_manager_provider_reads_seeded_inventory(self):
        provider = SecretsManagerSecretProvider(
            "us-east-1", aws_settings=aws_client_credentials("development")
        )
        signing_key = asyncio.run(provider.get_secret("improve/auth/token-signing-key"))
        self.assertTrue(signing_key.startswith("dummy-"))

    def test_secrets_carry_no_aws_credentials(self):
        provider = SecretsManagerSecretProvider(
            "us-east-1", aws_settings=aws_client_credentials("development")
        )
        raw = asyncio.run(provider.get_secret("improve/email/ses-smtp-credentials"))
        self.assertTrue(raw.startswith("dummy-"))
        self.assertNotIn("aws_access_key_id", raw)

    def test_boto3_ses_sender_delivers_email(self):
        _bootstrap_ses()
        sender = Boto3SESEmailSender(
            sender_address=SENDER,
            region_name="us-east-1",
            aws_settings=aws_client_credentials("development"),
        )
        asyncio.run(
            sender.send("learner@example.com", "Integration test", "Hello from boto3 SES")
        )
        self.assertIsNotNone(sender.last_message_id)


if __name__ == "__main__":
    unittest.main()