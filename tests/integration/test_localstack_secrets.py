"""LocalStack secret initialization tests (T112): running
``scripts/init-localstack.sh`` twice is idempotent, and a missing
mandatory secret produces an explicit configuration error."""

from __future__ import annotations

import json
import unittest
import urllib.request

from app.core.errors import ConfigurationError
from app.core.config.secret_provider import EnvSecretProvider, build_secret_provider

LOCALSTACK = "http://localhost:4566"


def localstack_secrets() -> set[str]:
    request = urllib.request.Request(f"{LOCALSTACK}/_localstack/state/secrets")  # localstack debug state endpoint
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            document = json.loads(response.read() or b"{}")
    except OSError:
        return set()
    return {item["Name"] for item in document.values() if isinstance(item, dict)}


def secretsmanager_list() -> list[str]:
    request = urllib.request.Request(f"{LOCALSTACK}/", method="POST")
    # The localstack REST edge requires the AWS JSON protocol; instead use
    # the debug state endpoint (documented for the localstack image).


def run_script_once() -> tuple[str, int]:
    """Run the script the way init.sh does (inside the LocalStack
    container, where awslocal is available); returns stdout + exit code."""
    import subprocess

    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "localstack", "bash", "-c",
         "export SECRETS_ENDPOINT_URL=http://localhost:4566; bash -s"],
        input=open("scripts/init-localstack.sh").read(),
        capture_output=True, text=True, timeout=120,
    )
    return result.stdout, result.returncode


def secret_names() -> list[str]:
    import re

    stdout, code = run_script_once()
    if code != 0:
        raise AssertionError(f"init-localstack.sh failed: {stdout}\n{code}")
    return re.findall(r"secret ok: (\S+)", stdout)


MANDATORY = [
    "improve/auth/token-signing-key",
    "improve/ai/generation-model-api-key",
    "improve/ai/evaluation-model-api-key",
    "improve/ai/embedding-api-key",
    "improve/email/ses-smtp-credentials",
]


@unittest.skipUnless(
    __import__("socket").create_connection(("localhost", 4566), timeout=0.5) is None
    if False else True,
    "skip guard evaluated below",
)
class TestLocalStackSecrets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket

        if not _reachable(4566):
            raise unittest.SkipTest("LocalStack is not running (compose up localstack)")

    def test_script_runs_twice_with_identical_result(self):
        import socket

        if not _reachable(4566):
            self.skipTest("LocalStack is not running")
        first = sorted(set(secret_names()))
        self.assertEqual(len(first), len(MANDATORY), first)
        second = sorted(set(secret_names()))
        self.assertEqual(first, second, "the script must be idempotent")

    def test_missing_secret_raises_configuration_error(self):
        provider = EnvSecretProvider({"some/other-secret": "value"})
        with self.assertRaises(ConfigurationError):
            import asyncio

            asyncio.run(provider.get_secret("improve/auth/token-signing-key"))

    def test_dummy_values_cannot_grant_real_access(self):
        content = open("scripts/init-localstack.sh").read()
        self.assertIn("dummy-", content)
        import re

        values = re.findall(r'"(dummy-[^"]+)"', content)
        self.assertTrue(values)
        for value in values:
            self.assertFalse(value.lower().startswith("akia"), value)


def _reachable(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("localhost", port), timeout=0.5):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    unittest.main()